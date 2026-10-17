"""Optional OMDb metadata. Separate from playback; never uploads a video or logs API keys."""

import hashlib
import json
import queue
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

from . import __version__
from .paths import data_dir
from .storage import atomic_json


class MovieLookupError(Exception):
    pass


@dataclass(frozen=True)
class MovieQuery:
    title: str
    year: str = ""
    imdb_id: str = ""


@dataclass(frozen=True)
class MovieDetails:
    title: str
    year: str = ""
    runtime: str = ""
    genre: str = ""
    plot: str = ""
    actors: str = ""
    director: str = ""
    imdb_id: str = ""
    imdb_rating: str = ""
    imdb_votes: str = ""
    rotten_rating: str = ""
    rotten_url: str = ""
    poster_url: str = ""
    updated_at: float = 0


@dataclass(frozen=True)
class MovieResult:
    details: MovieDetails
    poster: bytes = b""
    cached: bool = False


def guess_movie(filename: str | Path) -> MovieQuery:
    stem = Path(filename).stem
    imdb = re.search(r"\btt\d{5,12}\b", stem, re.I)
    if imdb:
        return MovieQuery(stem, imdb_id=imdb.group().lower())
    years = [
        match
        for match in re.finditer(r"(?<!\d)((?:18|19|20)\d{2})(?!\d)", stem)
        if 1880 <= int(match.group()) <= datetime.now().year + 1
    ]
    year = years[-1].group() if years else ""
    title = stem[: years[-1].start()] if years else stem
    title = re.sub(r"\[[^\]]*\]", " ", title)
    title = re.sub(r"[._]+", " ", title)
    noise = re.search(
        r"\b(?:480p|720p|1080p|2160p|4k|web[ -]?dl|webrip|bluray|b[dr]rip|hdrip|dvdrip|remux|x26[45]|h26[45]|hevc|aac|eac3|dts|dublado|legendado|10bit|s\d{1,2}e\d{1,2})\b",
        title,
        re.I,
    )
    if noise and noise.start() > 0:
        title = title[: noise.start()]
    title = re.sub(r"\s+", " ", title).strip(" .-_[]()") or stem
    return MovieQuery(title, year)


def clean(value) -> str:
    return "" if value in (None, "N/A", "") else str(value)


def parse_details(raw: dict) -> MovieDetails:
    if raw.get("Response") != "True" or not raw.get("Title"):
        raise MovieLookupError(
            "Filme não encontrado. Use Corrigir identificação para informar o título ou o link IMDb."
        )
    ratings = {
        row.get("Source"): clean(row.get("Value"))
        for row in raw.get("Ratings", [])
        if isinstance(row, dict)
    }
    imdb_id = clean(raw.get("imdbID"))
    if not re.fullmatch(r"tt\d{5,12}", imdb_id):
        imdb_id = ""
    rotten_url = clean(raw.get("tomatoURL"))
    parsed = urlsplit(rotten_url)
    if parsed.hostname not in {
        "www.rottentomatoes.com",
        "rottentomatoes.com",
    } or not parsed.path.startswith("/m/"):
        rotten_url = ""
    elif parsed.scheme in {"http", "https"}:
        rotten_url = "https://www.rottentomatoes.com" + parsed.path
    else:
        rotten_url = ""
    return MovieDetails(
        title=clean(raw["Title"]),
        year=clean(raw.get("Year")),
        runtime=clean(raw.get("Runtime")),
        genre=clean(raw.get("Genre")),
        plot=clean(raw.get("Plot")),
        actors=clean(raw.get("Actors")),
        director=clean(raw.get("Director")),
        imdb_id=imdb_id,
        imdb_rating=clean(raw.get("imdbRating")),
        imdb_votes=clean(raw.get("imdbVotes")),
        rotten_rating=ratings.get("Rotten Tomatoes", ""),
        rotten_url=rotten_url,
        poster_url=clean(raw.get("Poster")),
        updated_at=time.time(),
    )


class MovieStore:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        self.config_path = self.root / "movie-settings.json"
        self.cache = self.root / "movie-cache"
        self.lock = threading.RLock()
        self.epoch = 0

    def settings(self):
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {"key": "", "automatic": True}
            return {"key": str(raw.get("key", "")), "automatic": bool(raw.get("automatic", True))}
        except (OSError, ValueError, TypeError):
            return {"key": "", "automatic": True}

    def save_settings(self, key: str, automatic: bool):
        key = key.strip()
        if key and not re.fullmatch(r"[A-Za-z0-9_-]{4,128}", key):
            raise ValueError("Informe apenas a chave recebida do OMDb, sem URL ou espaços.")
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock:
            self.epoch += 1
            atomic_json(self.config_path, {"key": key, "automatic": automatic})

    def cache_path(self, query: MovieQuery):
        identity = f"{query.title.casefold()}|{query.year}|{query.imdb_id}"
        return self.cache / (hashlib.sha256(identity.encode()).hexdigest() + ".json")


class MovieClient:
    def __init__(self, store: MovieStore, opener=urlopen):
        self.store = store
        self.opener = opener

    def _get(self, url: str, limit: int):
        request = Request(
            url, headers={"User-Agent": f"LocalCast/{__version__}", "Accept": "application/json,image/*"}
        )
        try:
            with self.opener(request, timeout=10) as response:
                data = response.read(limit + 1)
            if len(data) > limit:
                raise MovieLookupError("A resposta da fonte de filmes excedeu o tamanho permitido.")
            return data
        except HTTPError as exc:
            message = (
                "Chave OMDb inválida ou não ativada. Confira Configurar filmes."
                if exc.code in (401, 403)
                else "A fonte de filmes está indisponível. Tente novamente mais tarde."
            )
            raise MovieLookupError(message) from None
        except (URLError, TimeoutError, OSError):
            raise MovieLookupError(
                "Sem resposta da fonte de filmes. A reprodução continua disponível."
            ) from None

    def _poster(self, url: str):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "m.media-amazon.com",
            "ia.media-imdb.com",
            "images-na.ssl-images-amazon.com",
            "img.omdbapi.com",
        }:
            return b""
        try:
            return self._get(url, 5_000_000)
        except MovieLookupError:
            return b""

    def lookup(self, query: MovieQuery, key: str, refresh=False, cache_epoch=None) -> MovieResult:
        with self.store.lock:
            epoch = self.store.epoch if cache_epoch is None else cache_epoch
        if not key:
            raise MovieLookupError(
                "Configure sua chave gratuita OMDb para buscar capa, notas e elenco."
            )
        cached_path = self.store.cache_path(query)
        poster_path = cached_path.with_suffix(".image")
        if not refresh:
            try:
                details = MovieDetails(**json.loads(cached_path.read_text(encoding="utf-8")))
                if time.time() - details.updated_at < 7 * 86400:
                    poster = poster_path.read_bytes() if poster_path.is_file() else b""
                    return MovieResult(details, poster, True)
            except (OSError, ValueError, TypeError):
                pass
        params = {"apikey": key, "r": "json", "plot": "short"}
        if query.imdb_id:
            params["i"] = query.imdb_id
        else:
            params["t"] = query.title
            if query.year:
                params["y"] = query.year
        payload = self._get("https://www.omdbapi.com/?" + urlencode(params), 1_000_000)
        try:
            raw = json.loads(payload)
        except (ValueError, TypeError):
            raise MovieLookupError("A fonte de filmes retornou uma resposta inválida.") from None
        if not isinstance(raw, dict):
            raise MovieLookupError("A fonte de filmes retornou uma resposta inválida.")
        if raw.get("Response") == "False" and any(
            word in str(raw.get("Error", "")).lower() for word in ("key", "limit")
        ):
            raise MovieLookupError(
                "Chave OMDb inválida ou limite de consultas atingido. Confira Configurar filmes."
            )
        details = parse_details(raw)
        poster = self._poster(details.poster_url)
        try:
            with self.store.lock:
                if epoch == self.store.epoch:
                    cached_path.parent.mkdir(parents=True, exist_ok=True)
                    atomic_json(cached_path, asdict(details))
                    poster_path.write_bytes(poster)
        except OSError:
            pass  # A cache error must not hide metadata already received.
        return MovieResult(details, poster)


class MovieWorker(QObject):
    finished = Signal(int, object)
    failed = Signal(int, str)

    def __init__(self, client):
        super().__init__()
        self.client = client
        self.commands = queue.Queue()
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._run, name="localcast-movies", daemon=True)
        self.thread.start()

    def submit(self, generation: int, query: MovieQuery, key: str, refresh=False):
        self.commands.put((generation, query, key, refresh, self.client.store.epoch))

    def close(self):
        self.closed.set()
        self.commands.put(None)

    def _run(self):
        while not self.closed.is_set():
            command = self.commands.get()
            if command is None:
                return
            # Skip pending files superseded while a bounded network request was running.
            while not self.commands.empty():
                command = self.commands.get()
                if command is None:
                    return
            generation, query, key, refresh, epoch = command
            if epoch != self.client.store.epoch:
                continue
            try:
                result = self.client.lookup(query, key, refresh, cache_epoch=epoch)
                if not self.closed.is_set():
                    self.finished.emit(generation, result)
            except Exception:
                # Do not forward arbitrary exception text: it might contain a URL/API key.
                message = (
                    "Não foi possível consultar o filme. Confira a fonte em Configurar filmes."
                )
                try:
                    raise
                except MovieLookupError as exc:
                    message = str(exc)
                except Exception:
                    pass
                if not self.closed.is_set():
                    self.failed.emit(generation, message)
