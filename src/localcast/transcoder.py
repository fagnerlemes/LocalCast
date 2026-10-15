"""One FFmpeg process per HLS session. No whole-file conversion before LOAD."""

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

from .file_io import read_shared_text
from .media import MediaInfo, SubtitleTrack
from .paths import process_options, tool_path
from .subtitles import bitmap_graph, text_filter

LOG = logging.getLogger(__name__)


def video_filter(info: MediaInfo, max_height: int) -> str:
    width = 1920 if max_height == 1080 else 1280
    fit = f"scale=w='min({width},iw)':h='min({max_height},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1"
    if info.hdr:
        # Requires FFmpeg with zscale (libzimg); fail clearly if unavailable.
        # Scale before float conversion to reduce cost for 4K input.
        return (
            fit
            + ",zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
        )
    return fit + ",format=yuv420p"


def build_command(
    info: MediaInfo,
    directory: Path,
    start: float = 0,
    max_height: int = 1080,
    ffmpeg: str | None = None,
    subtitle: SubtitleTrack | None = None,
) -> list[str]:
    if max_height not in (720, 1080):
        raise ValueError("Resolução alvo deve ser 720 ou 1080.")
    if start < 0 or (info.duration > 0 and start >= info.duration):
        raise ValueError("Posição fora do vídeo.")
    fps = min(info.fps, 30) if info.fps > 0 else 30
    command = [
        ffmpeg or tool_path("ffmpeg"),
        "-hide_banner",
        "-nostdin",
        "-y",
        "-loglevel",
        "warning",
        "-stats_period",
        "1",
        "-progress",
        "pipe:1",
    ]
    if start:
        command += ["-ss", f"{start:.3f}"]
    if subtitle and subtitle.kind == "unsupported":
        raise ValueError("Formato de legenda não suportado.")
    bitmap = subtitle is not None and subtitle.kind == "bitmap"
    command += ["-i", str(info.path), "-map", "[vout]" if bitmap else f"0:{info.video_index}"]
    if info.audio_index is not None:
        command += ["-map", f"0:{info.audio_index}"]
    base = video_filter(info, max_height)
    if bitmap:
        command += ["-filter_complex", bitmap_graph(info, subtitle, base)]
    else:
        command += ["-vf", text_filter(info, subtitle, base, start) if subtitle else base]
    command += [
        "-sn",
        "-dn",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-r",
        f"{fps:.6f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-profile:v",
        "high",
        "-level:v",
        "4.1",
        "-pix_fmt",
        "yuv420p",
        "-maxrate",
        "6M",
        "-bufsize",
        "12M",
        "-refs",
        "3",
        "-g",
        str(round(fps * 4)),
        "-keyint_min",
        str(round(fps * 4)),
        "-sc_threshold",
        "0",
        "-force_key_frames",
        "expr:gte(t,n_forced*4)",
        "-c:a",
        "aac",
        "-profile:a",
        "aac_low",
        "-b:a",
        "192k",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-f",
        "hls",
        "-hls_segment_type",
        "mpegts",
        "-hls_time",
        "4",
        "-hls_playlist_type",
        "event",
        "-hls_list_size",
        "0",
        "-hls_flags",
        "independent_segments+temp_file",
        "-hls_segment_filename",
        str(directory / "segment_%06d.ts"),
        str(directory / "stream.m3u8"),
    ]
    return command


class HlsJob:
    def __init__(
        self,
        info: MediaInfo,
        cache_root: Path,
        start: float = 0,
        max_height: int = 1080,
        ffmpeg: str | None = None,
        subtitle: SubtitleTrack | None = None,
    ):
        cache_root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(cache_root).free < 512 * 1024 * 1024:
            raise RuntimeError("Menos de 512 MB livres para cache HLS.")
        self.directory = Path(tempfile.mkdtemp(prefix="session-", dir=cache_root))
        self.info = info
        self.offset = start
        self.subtitle = subtitle
        self._lock = threading.Lock()
        self._tail = deque(maxlen=40)
        self.speed = 0.0
        self.encoded_seconds = 0.0
        self.error: str | None = None
        self._stop = threading.Event()
        codecs = "avc1.640029" + (",mp4a.40.2" if info.audio_codec else "")
        (self.directory / "master.m3u8").write_text(
            f'#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=7500000,CODECS="{codecs}"\nstream.m3u8\n',
            encoding="ascii",
        )
        try:
            self.command = build_command(info, self.directory, start, max_height, ffmpeg, subtitle)
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                **process_options(),
            )
        except Exception:
            shutil.rmtree(self.directory, ignore_errors=True)
            raise
        self._threads = [
            threading.Thread(target=self._read_progress, daemon=True),
            threading.Thread(target=self._read_errors, daemon=True),
            threading.Thread(target=self._guard_disk, daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        LOG.info("HLS iniciado: offset=%.3f alvo=%sp", start, max_height)

    def _read_progress(self):
        for line in self.process.stdout:
            key, _, value = line.strip().partition("=")
            try:
                with self._lock:
                    if key == "speed":
                        self.speed = float(value.rstrip("x"))
                    elif key == "out_time_us":
                        self.encoded_seconds = max(0, int(value) / 1_000_000)
            except ValueError:
                pass

    def _read_errors(self):
        for line in self.process.stderr:
            with self._lock:
                self._tail.append(line.rstrip())
            LOG.warning("ffmpeg: %s", line.rstrip())
            if "failed to rename file" in line and "stream.m3u8.tmp" in line:
                self._publish_pending_playlist()

    def _publish_pending_playlist(self):
        # Windows can reject replacing a briefly open destination even with shared handles.
        # FFmpeg may exit with code 0 after that failure, so publish its completed temp file.
        temporary = self.directory / "stream.m3u8.tmp"
        destination = self.directory / "stream.m3u8"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not self._stop.is_set():
            try:
                os.replace(temporary, destination)
                LOG.info("Playlist HLS republicada após bloqueio de arquivo no Windows")
                return
            except FileNotFoundError:
                return  # Already published by FFmpeg; no fixed filename from stderr is executed.
            except PermissionError:
                self._stop.wait(0.02)
        self.error = "Windows bloqueou a atualização da playlist HLS. Pare e tente novamente."
        LOG.error(self.error)

    def wait_finished(self, timeout=90):
        self.process.wait(timeout=timeout)
        for thread in self._threads[:2]:
            thread.join(timeout=4)

    def _guard_disk(self):
        while not self._stop.wait(3):
            if self.process.poll() is not None:
                return
            if shutil.disk_usage(self.directory).free < 256 * 1024 * 1024:
                self.error = "Cache HLS interrompido: menos de 256 MB livres no disco."
                self.process.terminate()
                LOG.error(self.error)
                return

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "speed": self.speed,
                "encoded_seconds": self.encoded_seconds,
                "returncode": self.process.poll(),
                "error": self.error,
                "stderr_tail": list(self._tail),
            }

    def wait_ready(self, timeout: float = 90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            playlist = self.directory / "stream.m3u8"
            if playlist.exists():
                text = read_shared_text(playlist)
                segments = [line for line in text.splitlines() if line and not line.startswith("#")]
                complete = all((self.directory / name).is_file() for name in segments)
                if complete and (len(segments) >= 2 or (segments and "#EXT-X-ENDLIST" in text)):
                    return
            code = self.process.poll()
            if code is not None and code != 0:
                raise RuntimeError(
                    "ffmpeg falhou: " + "\n".join(self.snapshot()["stderr_tail"])[-2500:]
                )
            if self.error:
                raise RuntimeError(self.error)
            time.sleep(0.1)
        raise TimeoutError(
            "HLS não produziu segmentos em 90 s. Verifique CPU, ffmpeg e o arquivo; tente 720p."
        )

    def close(self):
        self._stop.set()
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        for thread in self._threads:
            thread.join(timeout=2)
        self.process.stdout.close()
        self.process.stderr.close()
        # A previous HTTP request can still hold a Windows file handle briefly.
        for attempt in range(6):
            try:
                shutil.rmtree(self.directory)
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(0.2)
        LOG.warning("Cache não removido (arquivo ocupado): %s", self.directory)
