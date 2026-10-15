"""LAN HTTP server: only explicitly registered files and immutable HLS segments."""

import io
import logging
import re
import secrets
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .file_io import open_shared_binary

LOG = logging.getLogger(__name__)


def lan_ip_for(host: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((host, 8009))  # Route selection only; does not send a UDP packet.
        address = sock.getsockname()[0]
    if address.startswith("127.") or address == "0.0.0.0":
        raise RuntimeError("Não foi possível escolher um IP LAN. Informe o IP do PC manualmente.")
    return address


def parse_range(header: str, size: int) -> tuple[int, int]:
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match or size <= 0:
        raise ValueError("Range inválido")
    first, last = match.groups()
    if not first:
        if not last or int(last) <= 0:
            raise ValueError("Range inválido")
        return max(0, size - int(last)), size - 1
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise ValueError("Range fora do arquivo")
    return start, end


@dataclass
class Resource:
    path: Path
    mime: str
    directory: bool = False
    name: str = "media.mp4"


class MediaServer:
    def __init__(self, bind: str = "0.0.0.0", port: int = 8765):
        self._resources: dict[str, Resource] = {}
        self._lock = threading.RLock()
        self._stats: dict[str, dict] = {}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                self.connection.settimeout(15)

            def end_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
                self.send_header(
                    "Access-Control-Expose-Headers", "Content-Length, Content-Range, Accept-Ranges"
                )
                self.send_header("Cache-Control", "no-store")
                super().end_headers()

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def do_HEAD(self):
                self._serve(head=True)

            def do_GET(self):
                self._serve(head=False)

            def _serve(self, head: bool):
                parts = unquote(urlsplit(self.path).path).strip("/").split("/")
                token = parts[0]
                try:
                    if parts == ["health"]:
                        body = b"LocalCast LAN OK\n"
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        if not head:
                            self.wfile.write(body)
                        return
                    resolved = owner.resolve(parts)
                    if resolved is None:
                        self.send_error(404, "Resource not registered")
                        owner.record(token, 404, head)
                        return
                    path, mime = resolved
                    # Copy tiny mutable playlists first; release Windows file handles before IO
                    # to a possibly slow receiver. Video and TS remain streamed from disk.
                    if path.suffix == ".m3u8":
                        with open_shared_binary(path) as reader:
                            source_stream = io.BytesIO(reader.read())
                    else:
                        source_stream = open_shared_binary(path)
                    with source_stream as source:
                        # Open first, then fstat: playlist may be replaced atomically.
                        import os

                        size = (
                            len(source.getbuffer())
                            if isinstance(source, io.BytesIO)
                            else os.fstat(source.fileno()).st_size
                        )
                        start, end, status = 0, size - 1, 200
                        range_header = self.headers.get("Range")
                        if range_header:
                            try:
                                start, end = parse_range(range_header, size)
                                status = 206
                            except ValueError:
                                self.send_response(416)
                                self.send_header("Content-Range", f"bytes */{size}")
                                self.send_header("Content-Length", "0")
                                self.end_headers()
                                owner.record(token, 416, head)
                                return
                        length = max(0, end - start + 1)
                        self.send_response(status)
                        self.send_header("Content-Type", mime)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Content-Length", str(length))
                        if status == 206:
                            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                        self.end_headers()
                        owner.record(token, status, head)
                        if head:
                            return
                        source.seek(start)
                        remaining = length
                        while remaining:
                            chunk = source.read(min(256 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    LOG.debug("Cliente HTTP desconectou")
                except FileNotFoundError:
                    self.send_error(404)
                    owner.record(token, 404, head)
                except OSError:
                    LOG.exception("Falha HTTP")
                    self.close_connection = True

            def log_message(self, fmt, *args):
                # Token itself is a capability; never include it in normal access logs.
                LOG.debug(
                    "HTTP %s: %s", self.client_address[0], args[1:] if len(args) > 1 else args
                )

        self.httpd = ThreadingHTTPServer((bind, port), Handler)
        self.httpd.daemon_threads = True
        self.httpd.block_on_close = False
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(
            target=self.httpd.serve_forever, name="localcast-http", daemon=True
        )
        self._thread.start()
        LOG.info("Servidor HTTP na porta %s", self.port)

    def register_file(self, path: Path, mime: str | None = None) -> str:
        name = "media.mkv" if path.suffix.lower() == ".mkv" else "media.mp4"
        mime = mime or ("video/x-matroska" if name == "media.mkv" else "video/mp4")
        return self._register(Resource(path.resolve(), mime, name=name))

    def register_hls(self, directory: Path) -> str:
        return self._register(Resource(directory.resolve(), "application/vnd.apple.mpegurl", True))

    def _register(self, resource: Resource) -> str:
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._resources[token] = resource
            self._stats[token] = {"get_ok": 0, "head_ok": 0, "errors": 0, "last_status": None}
        return token

    def resolve(self, parts: list[str]) -> tuple[Path, str] | None:
        with self._lock:
            resource = self._resources.get(parts[0])
        if not resource:
            return None
        if not resource.directory:
            return (
                (resource.path, resource.mime)
                if len(parts) == 2 and parts[1] == resource.name
                else None
            )
        if len(parts) != 2 or not re.fullmatch(
            r"(?:master|stream)\.m3u8|segment_\d{6,}\.ts", parts[1]
        ):
            return None
        path = resource.path / parts[1]
        if path.is_symlink() or not path.is_file():
            return None
        return path, "video/mp2t" if path.suffix == ".ts" else resource.mime

    def url(self, token: str, advertised_ip: str, name: str = "media.mp4") -> str:
        socket.inet_aton(advertised_ip)
        return f"http://{advertised_ip}:{self.port}/{token}/{name}"

    def record(self, token: str, status: int, head: bool):
        with self._lock:
            if token in self._stats:
                row = self._stats[token]
                row["head_ok" if head else "get_ok"] += int(status in (200, 206))
                row["errors"] += int(status >= 400)
                row["last_status"] = status

    def stats(self, token: str | None) -> dict:
        with self._lock:
            return dict(self._stats.get(token, {}))

    def unregister(self, token: str):
        with self._lock:
            self._resources.pop(token, None)
            self._stats.pop(token, None)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self._thread.join(timeout=2)
