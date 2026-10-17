"""Playback orchestration; called serially, never from the GUI thread."""

import logging
import math
import socket
import threading
import time
from pathlib import Path

from .cast_client import CastClient, Device
from .history import PlaybackTracker, VideoIdentity
from .http_server import MediaServer, lan_ip_for
from .media import MediaInfo, probe
from .paths import data_dir
from .transcoder import HlsJob
from .ui_assets import asset_path

LOG = logging.getLogger(__name__)


class PlaybackSession:
    def __init__(self, port: int = 8765, cast_client=None, history=None):
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
        self.standby_format = None
        self.device = None
        self.token = None
        self.url = None
        self.cover_token = None
        self.cover_url = None
        self.display_title = None
        self.ip = None
        self.mode = None
        self.offset = 0.0
        self.max_height = 1080
        self.encoder_mode = "auto"
        self.ahead_seconds = 90
        self._status_requested = 0.0
        self._clock_confirmed = False
        self.last_failure = None
        self._lock = threading.RLock()
        self.history = history
        self.tracker = None
        self.history_warning = history.error if history else None
        self._history_stop = threading.Event()
        self._history_thread = None
        if history:
            self._history_thread = threading.Thread(target=self._history_loop, daemon=True)
            self._history_thread.start()

    def _history_loop(self):
        requested = 0.0
        while not self._history_stop.wait(.5):
            try:
                if self.mode and time.monotonic() - requested >= 5:
                    requested = time.monotonic()
                    self.client.request_status()
                self._checkpoint()
            except Exception as exc:
                self.history_warning = f'Não foi possível salvar o progresso: {exc}'

    def _checkpoint(self, force=False):
        with self._lock:
            if not self.tracker:
                return
            status = self.client.reported_snapshot()
            status['matches_media'] = bool(self.url and status.get('content_id') == self.url)
            raw = status.get('current_time')
            status['reported_position'] = raw + self.offset if isinstance(raw, (int, float)) else None
            try:
                self.tracker.observe(status, force=force)
            except Exception as exc:
                self.history_warning = f'Histórico indisponível; reprodução preservada: {exc}'

    def _prepare_tracker(self, position):
        if self.history:
            with self._lock:
                self.tracker = PlaybackTracker(
                    self.history, VideoIdentity.from_path(self.source_info.path),
                    self.source_info.duration, position,
                    self.client.reported_snapshot().get('status_serial', 0),
                )

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
        picture = asset_path('localcast-espera-1280x720.jpg')
        if not picture.is_file() and not clip.is_file():
            raise FileNotFoundError("Tela de espera ausente. Preserve a pasta assets do LocalCast.")
        self.stop()
        with self._lock:
            self.last_failure = None
            self.info, self.source_info, self.subtitle = None, None, None
        try:
            self._connect_device(device, advertised_ip)
            self._owns_receiver = True
            self.standby_active = True
            if picture.is_file():
                self.token = self.server.register_file(picture, 'image/jpeg')
                self.url = self.server.url(self.token, self.ip, 'media.jpg')
                try:
                    self.client.load(self.url, 'image/jpeg', 'LocalCast • By Fagner Lemes', image=True)
                    self.standby_format = 'image'
                    return
                except Exception:
                    if not clip.is_file():
                        raise
                    LOG.warning('Receiver não confirmou a imagem; tentando vídeo de compatibilidade.', exc_info=True)
                    self._release_media()
            self.token = self.server.register_file(clip, 'video/mp4')
            self.url = self.server.url(self.token, self.ip)
            self.client.load(self.url, 'video/mp4', 'LocalCast • By Fagner Lemes')
            self.client.command('pause')
            self.standby_format = 'video-fallback'
        except Exception as exc:
            self._remember_failure(exc)
            self.stop()
            raise

    def stop_to_standby(self):
        device, ip = self.device, self.ip
        if device and self._owns_receiver:
            # One STOP, then reconnect/load. A transient connection snapshot after
            # STOP must not silently skip the requested return to the idle artwork.
            self.show_standby(device, ip)
        else:
            self.stop()

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
        encoder_mode: str = "auto",
        ahead_seconds: int = 90,
        start_position: float = 0,
        display_title: str | None = None,
        cover: bytes = b'',
    ):
        if not math.isfinite(start_position) or start_position < 0 or (
            start_position and (info.duration <= 0 or start_position >= info.duration)
        ):
            raise ValueError('Posição de retomada inválida para este arquivo.')
        if encoder_mode not in {"auto", "cpu"} or not 30 <= ahead_seconds <= 300:
            raise ValueError("Configuração de processamento inválida.")
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
            self.encoder_mode, self.ahead_seconds = encoder_mode, ahead_seconds
            self.display_title = display_title or info.path.name
        try:
            self._connect_device(device, advertised_ip)
            if cover:
                try:
                    self.cover_token = self.server.register_image(cover)
                    self.cover_url = self.server.url(self.cover_token, self.ip, 'cover')
                except ValueError:
                    LOG.warning('Capa indisponível ou incompatível; reproduzindo sem imagem.')
            with self._lock:
                self.mode = self._selected_mode()
            self._load_from(start_position)
        except Exception as exc:
            # Preserve failure snapshot in log before releasing URLs and FFmpeg.
            self._remember_failure(exc)
            self.stop()
            raise

    def _load_from(self, position: float):
        with self._lock:
            self.offset = position if self.mode == "hls" else 0.0
            self._clock_confirmed = False
        self._prepare_tracker(position)
        if self.mode == "hls":
            kwargs = {"subtitle": self.subtitle} if self.subtitle is not None else {}
            job = HlsJob(
                self.info, data_dir() / "cache", position, self.max_height,
                encoder_mode=self.encoder_mode, ahead_seconds=self.ahead_seconds,
                playback=self._hls_clock, **kwargs,
            )
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
        self.client.load(self.url, mime, self.display_title, hls=self.mode == "hls",
                         cover_url=self.cover_url, duration=self.source_info.duration, **kwargs)
        if position and self.history:
            self._confirm_position(position)
        self._checkpoint()

    def _confirm_position(self, position):
        deadline = time.monotonic() + 8
        seek_sent = False
        while time.monotonic() < deadline:
            status = self.client.reported_snapshot()
            raw = status.get('current_time')
            if (status.get('content_id') == self.url and status.get('connected')
                    and status.get('player_state') in {'PLAYING', 'PAUSED'}
                    and isinstance(raw, (int, float))
                    and position - 5 <= raw + self.offset <= position + 30):
                return
            if self.mode != 'hls' and status.get('supports_seek') and not seek_sent:
                self.client.command('seek', position)
                seek_sent = True
            self.client.request_status()
            time.sleep(.5)
        raise RuntimeError('O Chromecast não confirmou a posição de retomada. '
                           'O ponto salvo foi preservado. Tente novamente ou use Começar do início.')

    def _hls_clock(self):
        # Called by the encoder governor, without acquiring the session lock.
        # A new LOAD must not inherit the previous video's clock, including after seek.
        if not self.url:
            return {"position": 0.0, "state": "PREPARING"}
        now = time.monotonic()
        if now - self._status_requested >= 5:
            self._status_requested = now
            try:
                self.client.request_status()
            except Exception:
                LOG.debug("Atualização do relógio Cast não confirmada", exc_info=True)
        status = self.client.snapshot()
        if not status.get("connected") or status.get("content_id") != self.url:
            if not self._clock_confirmed:
                return {"position": 0.0, "state": "PREPARING"}
            return {"position": None, "state": "UNKNOWN"}
        if status.get("status_age_seconds", 0) > 15:
            return {"position": None, "state": "UNKNOWN"}
        self._clock_confirmed = True
        return {"position": status.get("current_time"), "state": status.get("player_state")}

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
            self._checkpoint(force=True)
            self._prepare_tracker(position)
            self.client.command("seek", position)
            if self.history:
                self._confirm_position(position)
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
        self._checkpoint(force=action == 'pause')

    def _release_media(self):
        self._checkpoint(force=True)
        if self.token and self.server:
            self.server.unregister(self.token)
        with self._lock:
            job = self.job
            self.token, self.url, self.job = None, None, None
            self.tracker = None
        if job:
            job.close()

    def stop(self):
        self._checkpoint(force=True)
        try:
            if self.mode or self.standby_active:
                self.client.command("stop")
        except Exception:
            LOG.warning("STOP não confirmado; liberando recursos locais", exc_info=True)
        finally:
            self._release_media()
            if self.cover_token and self.server:
                self.server.unregister(self.cover_token)
            with self._lock:
                self.cover_token, self.cover_url, self.display_title = None, None, None
                self.mode, self.offset = None, 0.0
                self.standby_active = False
                self.standby_format = None

    def snapshot(self):
        with self._lock:
            status = self.client.snapshot()
            status["position"] = (status.get("current_time") or 0) + self.offset
            status["total_duration"] = self.info.duration if self.info else 0
            status["mode"] = self.mode
            status["standby_active"] = self.standby_active
            status['standby_format'] = self.standby_format
            status["offset"] = self.offset
            status["lan_ip"] = self.ip
            status["port"] = self.server.port if self.server else self.port
            status["http"] = self.server.stats(self.token) if self.server else {}
            status['artwork'] = {'available': bool(self.cover_url),
                                 'http': self.server.stats(self.cover_token) if self.server else {}}
            status["transcode"] = self.job.snapshot() if self.job else None
            if status["transcode"] and status["transcode"].get("buffer_target_seconds"):
                status["transcode"]["buffer_ahead_seconds"] = max(
                    0, status["transcode"]["published_seconds"] - (status.get("current_time") or 0)
                )
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
            status["history_warning"] = self.history_warning
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
        self._history_stop.set()
        try:
            self.disconnect()
        finally:
            if self._history_thread:
                self._history_thread.join(timeout=3)
