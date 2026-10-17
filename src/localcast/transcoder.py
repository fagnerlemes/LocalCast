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

import psutil

from .buffer_budget import BufferBudget
from .encoders import CPU, EncoderPlan, encoder_plans, encoding_options
from .file_io import read_shared_text
from .media import MediaInfo, SubtitleTrack
from .paths import process_options, tool_path
from .process_guard import ProcessGuard
from .storage import mark_session
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
    plan: EncoderPlan = CPU,
    paced: bool = False,
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
        "0.25",
        "-progress",
        "pipe:1",
    ]
    if start:
        command += ["-ss", f"{start:.3f}"]
    if paced:
        command += ["-readrate", "4", "-readrate_initial_burst", "12", "-readrate_catchup", "4"]
    if plan.cuda_decode:
        command += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    if subtitle and subtitle.kind == "unsupported":
        raise ValueError("Formato de legenda não suportado.")
    bitmap = subtitle is not None and subtitle.kind == "bitmap"
    command += ["-i", str(info.path), "-map", "[vout]" if bitmap else f"0:{info.video_index}"]
    if info.audio_index is not None:
        command += ["-map", f"0:{info.audio_index}"]
    base = video_filter(info, max_height)
    if plan.cuda_scale:
        width = 1920 if max_height == 1080 else 1280
        base = (
            f"scale_cuda=w='min({width},iw)':h='min({max_height},ih)':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2:format=yuv420p,setsar=1"
        )
    elif plan.cuda_decode:
        download_format = "p010le" if info.pixel_format in {"yuv420p10le", "p010le"} else "nv12"
        base = f"hwdownload,format={download_format}," + base
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
        *encoding_options(plan),
        "-profile:v",
        "high",
        "-level:v",
        "4.1",
        "-pix_fmt",
        "cuda" if plan.cuda_scale else "yuv420p",
        "-maxrate",
        "6M",
        "-bufsize",
        "12M",
        "-g",
        str(round(fps * 4)),
        "-keyint_min",
        str(round(fps * 4)),
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
        encoder_mode: str = "cpu",
        ahead_seconds: int = 0,
        playback=None,
    ):
        self.budget = BufferBudget(ahead_seconds) if ahead_seconds else None
        self._playback = playback
        self._ffmpeg = ffmpeg or tool_path("ffmpeg")
        self._plans = encoder_plans(self._ffmpeg, encoder_mode, info, subtitle)
        self._plan_index = 0
        self.fallbacks = []
        self._control_lock = threading.RLock()
        self._restarting = False
        self._suspended = False
        self._controlled = None
        self._paused_total = 0.0
        self._pause_started = 0.0
        self._published_seconds = 0.0
        self._playlist_stamp = None
        self.control_warning = None
        self._threads = []
        self._readers = []
        cache_root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(cache_root).free < 512 * 1024 * 1024:
            raise RuntimeError("Menos de 512 MB livres para cache HLS.")
        self.directory = Path(tempfile.mkdtemp(prefix="session-", dir=cache_root))
        self.info = info
        self.max_height = max_height
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
            self._spawn()
        except Exception:
            shutil.rmtree(self.directory, ignore_errors=True)
            raise
        for target in (self._guard_disk, self._governor):
            thread = threading.Thread(target=target, daemon=True)
            self._threads.append(thread)
            thread.start()
        LOG.info("HLS iniciado: offset=%.3f alvo=%sp", start, max_height)

    def _spawn(self):
        self.plan = self._plans[self._plan_index]
        self.command = build_command(
            self.info, self.directory, self.offset, self.max_height,
            self._ffmpeg, self.subtitle, self.plan, paced=self.budget is not None,
        )
        self._run_started = time.monotonic()
        self._guard = ProcessGuard()
        self.process = self._guard.spawn(
            self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            **process_options(),
        )
        try:
            mark_session(self.directory, self.process)
        except Exception:
            self._guard.close()
            self.process.wait(timeout=5)
            self.process.stdout.close()
            self.process.stderr.close()
            raise
        try:
            # This PID is obtained exclusively from our own Popen, never process enumeration.
            self._controlled = psutil.Process(self.process.pid)
            self._controlled.create_time()
        except psutil.Error:
            self._controlled = None
        self._readers = [threading.Thread(target=target, args=(self.process,), daemon=True)
                         for target in (self._read_progress, self._read_errors)]
        self._threads.extend(self._readers)
        for thread in self._readers:
            thread.start()
        LOG.info("Encoder iniciado: %s", self.plan.label)

    def _read_progress(self, process):
        for line in process.stdout:
            key, _, value = line.strip().partition("=")
            try:
                with self._lock:
                    if key == "speed":
                        self.speed = float(value.rstrip("x"))
                    elif key == "out_time_us":
                        self.encoded_seconds = max(0, int(value) / 1_000_000)
            except ValueError:
                pass

    def _read_errors(self, process):
        for line in process.stderr:
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
        for thread in self._readers:
            thread.join(timeout=4)

    def _suspend(self, suspended):
        if suspended == self._suspended or self.process.poll() is not None:
            return
        if self._controlled is None:
            raise RuntimeError("Controle do processo indisponível; conversão seguirá sem limite.")
        if suspended:
            self._controlled.suspend()
            self._pause_started = time.monotonic()
        else:
            self._controlled.resume()
            self._paused_total += time.monotonic() - self._pause_started
        self._suspended = suspended
        LOG.info("Conversão %s: reserva de %.1fs", "em descanso" if suspended else "retomada",
                 self.budget.ahead if self.budget else 0)

    def _published_duration(self):
        path = self.directory / "stream.m3u8"
        try:
            stamp = path.stat().st_mtime_ns
            if stamp == self._playlist_stamp:
                return self._published_seconds
            duration, pending = 0.0, 0.0
            for line in read_shared_text(path).splitlines():
                if line.startswith("#EXTINF:"):
                    pending = float(line[8:].split(",")[0])
                elif line and not line.startswith("#"):
                    if Path(line).name != line or not (self.directory / line).is_file():
                        break
                    duration += max(0, pending)
                    pending = 0.0
            self._published_seconds = max(self._published_seconds, duration)
            self._playlist_stamp = stamp
        except (OSError, ValueError):
            pass
        return self._published_seconds

    def _governor(self):
        if not self.budget:
            return
        while not self._stop.wait(0.2):
            with self._control_lock:
                if self._restarting:
                    continue
                if self.process.poll() is not None:
                    continue
                if self.control_warning:
                    continue
                try:
                    clock = self._playback() if self._playback else {
                        "position": 0.0, "state": "PREPARING",
                    }
                except Exception:
                    clock = {"position": None, "state": "UNKNOWN"}
                finishing = self.info.duration > 0 and (
                    self.offset + self.encoded_seconds >= self.info.duration - 2
                )
                wanted = self.budget.decide(
                    self._published_duration(), clock.get("position"),
                    clock.get("state"), finishing=finishing,
                )
                try:
                    self._suspend(wanted)
                except (psutil.Error, RuntimeError) as exc:
                    self.control_warning = str(exc)
                    LOG.warning("Controle de antecipação indisponível: %s", exc)
                    if self._suspended:
                        try:
                            self._suspend(False)
                        except (psutil.Error, RuntimeError):
                            self.error = "Não foi possível retomar FFmpeg; transmissão interrompida."
                            self.process.kill()

    def _stop_process(self):
        with self._control_lock:
            if self.process.poll() is None:
                try:
                    self._suspend(False)
                except (psutil.Error, RuntimeError):
                    pass
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        for thread in self._readers:
            thread.join(timeout=4)
        self.process.stdout.close()
        self.process.stderr.close()
        self._guard.close()

    def _fallback(self):
        if self._plan_index + 1 >= len(self._plans):
            return False
        LOG.warning("Encoder %s falhou antes do LOAD; tentando alternativa.", self.plan.label)
        self._restarting = True
        try:
            self._stop_process()
            detail = "\n".join(self._tail)[-600:]
            self.fallbacks.append({"encoder": self.plan.label, "reason": detail})
            with self._control_lock:
                for path in self.directory.iterdir():
                    if path.name not in {"master.m3u8", ".owner.json"}:
                        path.unlink(missing_ok=True)
                self._plan_index += 1
                with self._lock:
                    self._tail.clear()
                    self.speed, self.encoded_seconds = 0.0, 0.0
                self._suspended = False
                self._paused_total = self._published_seconds = 0.0
                self._playlist_stamp = None
                self.control_warning = None
                if self.budget:
                    self.budget.suspended = False
                self._spawn()
        finally:
            self._restarting = False
        return True

    def _guard_disk(self):
        while not self._stop.wait(3):
            if self.process.poll() is not None:
                continue
            if shutil.disk_usage(self.directory).free < 256 * 1024 * 1024:
                self.error = "Cache HLS interrompido: menos de 256 MB livres no disco."
                self.process.terminate()
                LOG.error(self.error)
                return

    def snapshot(self) -> dict:
        with self._lock:
            paused = (time.monotonic() - self._pause_started) if self._suspended else 0
            active_time = max(0.001, time.monotonic() - self._run_started - self._paused_total - paused)
            return {
                "speed": self.encoded_seconds / active_time,
                "reported_speed": self.speed,
                "encoded_seconds": self.encoded_seconds,
                "published_seconds": self._published_duration(),
                "returncode": self.process.poll(),
                "error": self.error,
                "stderr_tail": list(self._tail),
                "encoder": self.plan.label,
                "hardware": self.plan.codec != "libx264",
                "fallbacks": list(self.fallbacks),
                "buffer_target_seconds": self.budget.target if self.budget else 0,
                "buffer_ahead_seconds": self.budget.ahead if self.budget else None,
                "resting": self._suspended,
                "control_warning": self.control_warning,
            }

    def wait_ready(self, timeout: float = 90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            playlist = self.directory / "stream.m3u8"
            if playlist.exists():
                text = read_shared_text(playlist)
                segments = [line for line in text.splitlines() if line and not line.startswith("#")]
                complete = all((self.directory / name).is_file() for name in segments)
                if complete and (len(segments) >= 3 or (segments and "#EXT-X-ENDLIST" in text)):
                    return
            code = self.process.poll()
            if code is not None and code != 0:
                if self._fallback():
                    continue
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
        self._stop_process()
        mark_session(self.directory, closed=True)
        for thread in self._threads:
            thread.join(timeout=2)
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
