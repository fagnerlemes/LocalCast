"""PyChromecast boundary. Network operations belong in the UI worker."""

import logging
import math
import threading
import time
from dataclasses import dataclass

import pychromecast

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class Device:
    uuid: str
    name: str
    host: str
    model: str


class _Listener:
    def __init__(self, owner, cast):
        self.owner = owner
        self.cast = cast

    def new_media_status(self, status):
        if self.owner.cast is not self.cast:
            return
        fields = (
            "player_state",
            "idle_reason",
            "current_time",
            "duration",
            "content_id",
            "content_type",
            "stream_type",
            "supports_pause",
            "supports_seek",
            "playback_rate",
            "media_session_id",
        )
        with self.owner._lock:
            self.owner._status = {field: getattr(status, field, None) for field in fields}
            self.owner._status_at = time.monotonic()
            self.owner._status_serial += 1

    def load_media_failed(self, queue_item_id, error_code):
        if self.owner.cast is not self.cast:
            return
        with self.owner._lock:
            self.owner._load_error = (
                f"Receiver LOAD_FAILED (código {error_code}, item {queue_item_id})."
            )
        LOG.error(self.owner._load_error)


class CastClient:
    def __init__(self):
        self._devices = {}
        self._browser = None
        self.cast = None
        self._lock = threading.RLock()
        self._status = {}
        self._status_at = time.monotonic()
        self._status_serial = 0
        self._load_error = None
        self._listeners = {}
        self._owns_receiver = False

    def discover(self, known_host: str | None = None) -> list[Device]:
        # Retain current discovery objects until the session has been stopped by caller.
        self.disconnect()
        self._dispose_discovery()
        casts, self._browser = pychromecast.get_chromecasts(
            tries=1, timeout=5, retry_wait=1, known_hosts=[known_host] if known_host else None
        )
        self._devices = {str(c.uuid): c for c in casts if c.cast_type == "cast"}
        return [
            Device(
                key, c.name or "Chromecast", c.cast_info.host, c.model_name or "modelo desconhecido"
            )
            for key, c in self._devices.items()
        ]

    def connect(self, uuid: str):
        cast = self._devices.get(uuid)
        if cast is None:
            raise RuntimeError("Dispositivo não está na busca atual. Busque novamente.")
        if self.cast is not cast:
            if self._owns_receiver:
                self.quit_receiver()
            self.disconnect()
            self.cast = cast
            if uuid not in self._listeners:
                listener = _Listener(self, cast)
                cast.media_controller.register_status_listener(listener)
                self._listeners[uuid] = listener
        cast.wait(timeout=15)
        if not cast.socket_client.is_connected:
            raise ConnectionError("Chromecast não conectou. Verifique rede e TCP 8009.")

    def load(self, url: str, mime: str, title: str, hls: bool = False, current_time: float = 0,
             *, image: bool = False, cover_url: str | None = None, duration: float = 0):
        if not self.cast:
            raise RuntimeError("Conecte um Chromecast primeiro.")
        with self._lock:
            self._load_error = None
            self._status = {}
        controller = self.cast.media_controller
        self._owns_receiver = True
        # TS is the conventional Cast HLS format; physical receiver acceptance must be tested.
        metadata = {'metadataType': 4 if image else 1, 'title': title}
        if image or cover_url:
            metadata['images'] = [{'url': url if image else cover_url}]
        options = {'metadata': metadata}
        if not image and math.isfinite(duration) and duration > 0:
            seconds = int(duration)
            metadata['subtitle'] = (
                f'Duração total: {seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'
            )
            if not hls:
                options['media_info'] = {'duration': duration}
            # A growing EVENT playlist is LIVE. A finite duration or premature ENDLIST
            # does not turn it into complete VOD and can break playback/remote seeking.
        controller.play_media(
            url,
            mime,
            title=title,
            autoplay=True,
            stream_type="NONE" if image else "LIVE" if hls else "BUFFERED",
            current_time=current_time,
            **options,
        )
        deadline = time.monotonic() + (10 if image else 30)
        while time.monotonic() < deadline:
            status = self.snapshot()
            if status.get("load_error"):
                raise RuntimeError(status["load_error"])
            if status.get("content_id") == url:
                if status.get("idle_reason") == "ERROR":
                    raise RuntimeError("Receiver retornou IDLE/ERROR ao carregar a mídia.")
                if status.get("player_state") in {"PLAYING", "PAUSED"}:
                    return
                if image and status.get('player_state') == 'IDLE' and not status.get('idle_reason'):
                    return  # Photos have no playback timeline on some receivers.
            time.sleep(0.1)
        raise TimeoutError(
            "Receiver não confirmou a imagem em 10 s." if image else
            "Receiver não confirmou PLAYING/PAUSED em 30 s. Consulte HTTP, LOAD_FAILED e logs."
        )

    def command(self, action: str, position: float | None = None):
        if not self.cast or not self.cast.socket_client.is_connected:
            raise ConnectionError("Sem conexão com o Chromecast.")
        controller = self.cast.media_controller
        if action == "seek":
            controller.seek(position, timeout=10)
        elif action in {"play", "pause", "stop"}:
            getattr(controller, action)(timeout=10)
        else:
            raise ValueError("Comando desconhecido")

    def reported_snapshot(self) -> dict:
        with self._lock:
            row = dict(self._status)
            row["status_age_seconds"] = time.monotonic() - self._status_at
            row["status_serial"] = self._status_serial
            row["load_error"] = self._load_error
        row["connected"] = bool(
            self.cast
            and self.cast.socket_client.is_connected
            and not getattr(self.cast.socket_client, "is_stopped", False)
        )
        row["app_id"] = self.cast.app_id if self.cast else None
        receiver = getattr(self.cast, 'status', None) if row['connected'] else None
        level = getattr(receiver, 'volume_level', None)
        row['volume_level'] = level if isinstance(level, (int, float)) and math.isfinite(level) else None
        row['volume_muted'] = bool(getattr(receiver, 'volume_muted', False))
        return row

    def set_volume(self, percent, target):
        """Device volume, independent of the media stream and of Windows volume."""
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError('Volume deve estar entre 0 e 100%.')
        if self.cast is not target or not target or not target.socket_client.is_connected:
            raise ConnectionError('O Chromecast mudou ou foi desconectado. Ajuste o volume novamente.')
        target.set_volume(percent / 100, timeout=5)
        if percent > 0 and getattr(getattr(target, 'status', None), 'volume_muted', False):
            target.set_volume_muted(False, timeout=5)
        return percent

    def snapshot(self) -> dict:
        row = self.reported_snapshot()
        if row.get("player_state") == "PLAYING":
            row["current_time"] = (row.get("current_time") or 0) + (
                row["status_age_seconds"] * (row.get("playback_rate") or 1)
            )
            if row.get("stream_type") != "LIVE" and row.get("duration"):
                row["current_time"] = min(row["current_time"], row["duration"])
        return row

    def request_status(self):
        if self.cast and self.cast.socket_client.is_connected:
            self.cast.media_controller.update_status()

    def disconnect(self):
        # PyChromecast 14 has register_status_listener, but no unregister counterpart.
        # Listeners ignore callbacks from devices no longer selected.
        self.cast = None
        self._owns_receiver = False
        with self._lock:
            self._status = {}
            self._load_error = None

    def quit_receiver(self):
        if not self.cast:
            return
        # Quit our default receiver, leaving other receiver applications alone.
        if self._owns_receiver and self.cast.app_id == "CC1AD845":
            if not self.cast.socket_client.is_connected:
                raise ConnectionError(
                    "Chromecast desconectado da rede; saída do receiver não confirmada."
                )
            self.cast.quit_app(timeout=10)
            LOG.info("Default Media Receiver encerrado")
        self._owns_receiver = False

    def _dispose_discovery(self):
        if self._browser:
            self._browser.stop_discovery()
            self._browser = None
        for cast in self._devices.values():
            try:
                cast.disconnect(timeout=3)
            except Exception:
                LOG.debug("Falha ao desconectar dispositivo", exc_info=True)
        self._devices = {}
        self._listeners = {}

    def close(self):
        self.disconnect()
        self._dispose_discovery()
