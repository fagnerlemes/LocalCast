"""Playback orchestration; called serially, never from the GUI thread."""

import logging
import socket
import threading
from pathlib import Path

from .cast_client import CastClient, Device
from .http_server import MediaServer, lan_ip_for
from .media import MediaInfo, probe
from .paths import data_dir
from .transcoder import HlsJob
from .ui_assets import asset_path

LOG = logging.getLogger(__name__)


class PlaybackSession:
    def __init__(self, port: int = 8765, cast_client=None):
        self.client = cast_client or CastClient()
        self.port = port
        self.server = None
        self.job = None
        self.info = None
        self.source_info = None
        self.subtitle = None
        self.force_hls = False
        self.original = False
        self._owns_receiver = False
        self.standby_active = False
        self.device = None
        self.token = None
        self.url = None
        self.ip = None
        self.mode = None
        self.offset = 0.0
        self.max_height = 1080
        self.last_failure = None
        self._lock = threading.RLock()

    def discover(self, known_host=None):
        self.stop()
        if self._owns_receiver:
            self.client.quit_receiver()
            self._owns_receiver = False
        self.last_failure = None
        if known_host:
            socket.inet_aton(known_host)
        return self.client.discover(known_host)

    def analyze(self, path: Path):
        # No change to the playing session until the new file actually gets cast.
        return probe(path)

    def _connect_device(self, device: Device, advertised_ip: str | None):
        self.client.connect(device.uuid)
        ip = advertised_ip or lan_ip_for(device.host)
        socket.inet_aton(ip)
        if ip.startswith("127.") or ip == "0.0.0.0":
            raise ValueError("Use o IP LAN do PC, não localhost ou 0.0.0.0.")
        if not self.server:
            self.server = MediaServer(port=self.port)
        with self._lock:
            self.device, self.ip = device, ip

    def show_standby(self, device: Device, advertised_ip: str | None = None):
        clip = asset_path("localcast-espera.mp4")
        if not clip.is_file():
            raise FileNotFoundError("Tela de espera ausente. Preserve a pasta assets do LocalCast.")
        self.stop()
        with self._lock:
            self.last_failure = None
            self.info, self.source_info, self.subtitle = None, None, None
        try:
            self._connect_device(device, advertised_ip)
            self.token = self.server.register_file(clip, "video/mp4")
            self.url = self.server.url(self.token, self.ip)
            self._owns_receiver = True
            self.standby_active = True
            # Default receiver UI cannot be customized. Load a silent still-video
            # and pause it after acknowledgement, retaining the artwork on screen.
            self.client.load(self.url, "video/mp4", "LocalCast • By Fagner Lemes")
            self.client.command("pause")
        except Exception as exc:
            self._remember_failure(exc)
            self.stop()
            raise

    def stop_to_standby(self):
        device, ip = self.device, self.ip
        self.stop()
        if device and self._owns_receiver and self.client.snapshot().get("connected"):
            self.show_standby(device, ip)

    def start(
        self,
        info: MediaInfo,
        device: Device,
        force_hls=False,
        max_height=1080,
        advertised_ip: str | None = None,
        *,
        audio_index: int | None = None,
        subtitle_index: int | None = None,
        original: bool = False,
    ):
        selected_info = (
            info
            if original or audio_index is None
            else info.with_audio(None if audio_index == -1 else audio_index)
        )
        subtitle = None if original else info.subtitle_track(subtitle_index)
        self.stop()
        with self._lock:
            self.last_failure = None
            self.source_info = info
            self.info, self.device = selected_info, device
            self.subtitle, self.force_hls = subtitle, force_hls
            self.original = original
            self.max_height = max_height
        try:
            self._connect_device(device, advertised_ip)
            with self._lock:
                self.mode = self._selected_mode()
            self._load_from(0)
        except Exception as exc:
            # Preserve failure snapshot in log before releasing URLs and FFmpeg.
            self._remember_failure(exc)
            self.stop()
            raise

    def _load_from(self, position: float):
        with self._lock:
            self.offset = position if self.mode == "hls" else 0.0
        if self.mode == "hls":
            kwargs = {"subtitle": self.subtitle} if self.subtitle is not None else {}
            job = HlsJob(self.info, data_dir() / "cache", position, self.max_height, **kwargs)
            with self._lock:
                self.job = job
            job.wait_ready()
            self.token = self.server.register_hls(job.directory)
            name, mime = "master.m3u8", "application/vnd.apple.mpegurl"
        else:
            name, mime = (
                ("media.mkv", "video/x-matroska")
                if self.info.path.suffix.lower() == ".mkv"
                else ("media.mp4", "video/mp4")
            )
            self.token = self.server.register_file(self.info.path, mime)
        self.url = self.server.url(self.token, self.ip, name)
        self._owns_receiver = True
        kwargs = (
            {"current_time": position} if self.mode in {"direct", "original"} and position else {}
        )
        self.client.load(self.url, mime, self.info.path.name, hls=self.mode == "hls", **kwargs)

    def _selected_mode(self):
        if self.original:
            return "original"
        return (
            "hls"
            if (
                self.force_hls
                or not self.info.direct_ok
                or self.subtitle is not None
                or self.info.audio_index != self.source_info.audio_index
            )
            else "direct"
        )

    def set_tracks(self, audio_index: int | None, subtitle_index: int | None):
        if not self.mode or not self.source_info:
            raise RuntimeError("Nenhuma sessão ativa.")
        if self.mode == "original":
            raise ValueError(
                "No modo Original, as faixas dependem do Chromecast. Escolha conversão automática e transmita novamente para selecionar faixas no LocalCast."
            )
        info = self.source_info.with_audio(None if audio_index in (None, -1) else audio_index)
        subtitle = self.source_info.subtitle_track(subtitle_index)
        snapshot = self.snapshot()
        position = max(0, snapshot.get("position", 0))
        if info.duration > 0:
            position = min(position, max(0, info.duration - 0.25))
        paused = snapshot.get("player_state") == "PAUSED"
        try:
            self.client.command("stop")
            self._release_media()
            self.info, self.subtitle = info, subtitle
            self.mode = self._selected_mode()
            self._load_from(position)
            if paused:
                self.client.command("pause")
        except Exception as exc:
            self._remember_failure(exc)
            self.stop()
            raise

    def seek(self, position: float):
        if self.mode is None or not self.info:
            raise RuntimeError("Nenhuma sessão ativa.")
        if not 0 <= position < self.info.duration:
            raise ValueError("Posição fora do vídeo.")
        if self.mode in {"direct", "original"}:
            self.client.command("seek", position)
            return
        # The receiver cannot seek into segments not encoded yet. Restart at source offset.
        paused = self.client.snapshot().get("player_state") == "PAUSED"
        try:
            self.client.command("stop")
            self._release_media()
            self._load_from(position)
            if paused:
                self.client.command("pause")
        except Exception as exc:
            self._remember_failure(exc)
            self.stop()
            raise

    def _remember_failure(self, exc):
        snapshot = self.snapshot()
        self.last_failure = {
            "message": str(exc),
            "session": {
                k: v for k, v in snapshot.items() if k not in {"content_id", "last_failure"}
            },
        }
        LOG.error("Falha de reprodução: %s", self.last_failure)

    def command(self, action: str):
        if not self.mode:
            raise RuntimeError("Nenhuma sessão ativa.")
        self.client.command(action)

    def _release_media(self):
        if self.token and self.server:
            self.server.unregister(self.token)
        with self._lock:
            job = self.job
            self.token, self.url, self.job = None, None, None
        if job:
            job.close()

    def stop(self):
        try:
            if self.mode or self.standby_active:
                self.client.command("stop")
        except Exception:
            LOG.warning("STOP não confirmado; liberando recursos locais", exc_info=True)
        finally:
            self._release_media()
            with self._lock:
                self.mode, self.offset = None, 0.0
                self.standby_active = False

    def snapshot(self):
        with self._lock:
            status = self.client.snapshot()
            status["position"] = (status.get("current_time") or 0) + self.offset
            status["total_duration"] = self.info.duration if self.info else 0
            status["mode"] = self.mode
            status["standby_active"] = self.standby_active
            status["offset"] = self.offset
            status["lan_ip"] = self.ip
            status["port"] = self.server.port if self.server else self.port
            status["http"] = self.server.stats(self.token) if self.server else {}
            status["transcode"] = self.job.snapshot() if self.job else None
            status["file_summary"] = self.info.summary() if self.info else None
            status["audio_index"] = self.info.audio_index if self.info else None
            status["subtitle_index"] = self.subtitle.index if self.subtitle else None
            status["subtitle_mode"] = (
                "definido pelo Chromecast"
                if self.mode == "original"
                else "incorporada ao vídeo"
                if self.subtitle
                else "sem legenda"
            )
            status["last_failure"] = self.last_failure
            return status

    def disconnect(self):
        self.stop()
        quit_error = None
        try:
            if self._owns_receiver:
                self.client.quit_receiver()
        except Exception as exc:
            quit_error = exc
            LOG.warning("Receiver não confirmou encerramento", exc_info=True)
        finally:
            try:
                self.client.close()
            finally:
                self._owns_receiver = False
                self.device = None
                if self.server:
                    self.server.close()
                    self.server = None
        if quit_error:
            raise RuntimeError(
                "Conexão local encerrada, mas o Chromecast não confirmou sair do receiver. Confira a rede."
            ) from quit_error

    def close(self):
        self.disconnect()
