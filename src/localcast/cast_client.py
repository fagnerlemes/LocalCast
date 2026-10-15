"""PyChromecast boundary. Network operations belong in the UI worker."""

import logging
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
        )
        with self.owner._lock:
            self.owner._status = {field: getattr(status, field, None) for field in fields}
            self.owner._status_at = time.monotonic()

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

    def load(self, url: str, mime: str, title: str, hls: bool = False, current_time: float = 0):
        if not self.cast:
            raise RuntimeError("Conecte um Chromecast primeiro.")
        with self._lock:
            self._load_error = None
            self._status = {}
        controller = self.cast.media_controller
        self._owns_receiver = True
        # TS is the conventional Cast HLS format; physical receiver acceptance must be tested.
        controller.play_media(
            url,
            mime,
            title=title,
            autoplay=True,
            stream_type="LIVE" if hls else "BUFFERED",
            current_time=current_time,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = self.snapshot()
            if status.get("load_error"):
                raise RuntimeError(status["load_error"])
            if status.get("content_id") == url:
                if status.get("idle_reason") == "ERROR":
                    raise RuntimeError("Receiver retornou IDLE/ERROR ao carregar a mídia.")
                if status.get("player_state") in {"PLAYING", "PAUSED"}:
                    return
            time.sleep(0.1)
        raise TimeoutError(
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

    def snapshot(self) -> dict:
        with self._lock:
            row = dict(self._status)
            row["load_error"] = self._load_error
            if row.get("player_state") == "PLAYING":
                row["current_time"] = (row.get("current_time") or 0) + (
                    time.monotonic() - self._status_at
                ) * (row.get("playback_rate") or 1)
                if row.get("stream_type") != "LIVE" and row.get("duration"):
                    row["current_time"] = min(row["current_time"], row["duration"])
        row["connected"] = bool(
            self.cast
            and self.cast.socket_client.is_connected
            and not getattr(self.cast.socket_client, "is_stopped", False)
        )
        row["app_id"] = self.cast.app_id if self.cast else None
        return row

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
