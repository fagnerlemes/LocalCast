import io
import json
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from PySide6.QtWidgets import QApplication

from localcast.movie_info import (
    MovieClient,
    MovieLookupError,
    MovieQuery,
    MovieStore,
    MovieWorker,
    guess_movie,
    parse_details,
)


@pytest.mark.parametrize(
    "filename,title,year,imdb",
    [
        ("The.Matrix.1999.1080p.BluRay.x264.mkv", "The Matrix", "1999", ""),
        ("Blade.Runner.2049.2017.2160p.HEVC.mkv", "Blade Runner 2049", "2017", ""),
        ("2012.2009.AAC.mp4", "2012", "2009", ""),
        ("Meu Filme (2020) [dublado].mkv", "Meu Filme", "2020", ""),
        ("Title.tt0133093.HEVC.mkv", "Title.tt0133093.HEVC", "", "tt0133093"),
    ],
)
def test_guess_title_excludes_release_tags_and_preserves_movie_numbers(filename, title, year, imdb):
    query = guess_movie(filename)
    assert (query.title, query.year, query.imdb_id) == (title, year, imdb)


def payload(**overrides):
    return dict(
        {
            "Response": "True",
            "Title": "Test movie",
            "Year": "1999",
            "Actors": "Actor A, Actor B",
            "imdbID": "tt0133093",
            "imdbRating": "8.7",
            "Poster": "https://m.media-amazon.com/images/test.jpg",
            "Ratings": [{"Source": "Rotten Tomatoes", "Value": "88%"}],
        },
        **overrides,
    )


def test_metadata_distinguishes_rating_sources_and_missing_values():
    details = parse_details(payload())
    assert details.imdb_rating == "8.7" and details.rotten_rating == "88%"
    assert details.actors == "Actor A, Actor B"
    details = parse_details(payload(imdbRating="N/A", Ratings=[], Poster="N/A"))
    assert not details.rotten_rating and not details.imdb_rating and not details.poster_url
    with pytest.raises(MovieLookupError, match="encontrado"):
        parse_details({"Response": "False", "Error": "Movie not found!"})


def test_api_uses_only_title_and_year_and_cache_does_not_contain_key(tmp_path):
    store = MovieStore(tmp_path)
    store.config_path.write_text("[]", encoding="utf-8")
    assert store.settings()["key"] == ""
    store.save_settings("PRIVATE_TEST_KEY", True)
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        assert timeout == 10
        body = (
            json.dumps(payload()).encode() if "omdbapi.com" in request.full_url else b"poster bytes"
        )
        return io.BytesIO(body)

    client = MovieClient(store, opener)
    query = guess_movie(r"C:\Private\The.Matrix.1999.1080p.HEVC.mkv")
    first = client.lookup(query, store.settings()["key"])
    assert first.details.rotten_rating == "88%" and first.poster == b"poster bytes"
    params = parse_qs(urlsplit(calls[0]).query)
    assert params["t"] == ["The Matrix"] and params["y"] == ["1999"]
    assert "Private" not in calls[0] and "HEVC" not in calls[0]
    assert "PRIVATE_TEST_KEY" not in store.cache_path(query).read_text()
    second = client.lookup(query, "PRIVATE_TEST_KEY")
    assert second.cached and len(calls) == 2
    client.lookup(query, "PRIVATE_TEST_KEY", refresh=True)
    assert len(calls) == 4


def test_lookup_by_imdb_and_credentials_are_hidden_in_errors(tmp_path):
    urls = []

    def denied(request, timeout):
        urls.append(request.full_url)
        raise HTTPError(request.full_url, 401, "PRIVATE_KEY", None, None)

    client = MovieClient(MovieStore(tmp_path), denied)
    with pytest.raises(MovieLookupError, match="inválida") as error:
        client.lookup(MovieQuery("ignored", imdb_id="tt0133093"), "PRIVATE_KEY")
    assert "PRIVATE_KEY" not in str(error.value)
    assert parse_qs(urlsplit(urls[0]).query)["i"] == ["tt0133093"]
    with pytest.raises(MovieLookupError, match="gratuita"):
        client.lookup(MovieQuery("any"), "")


def test_quota_failure_and_poster_failure_do_not_replace_movie(tmp_path):
    def quota(request, timeout):
        return io.BytesIO(b'{"Response":"False","Error":"Request limit reached!"}')

    with pytest.raises(MovieLookupError, match="limite"):
        MovieClient(MovieStore(tmp_path), quota).lookup(MovieQuery("Test"), "key123")

    def no_poster(request, timeout):
        if "omdbapi.com" in request.full_url:
            return io.BytesIO(json.dumps(payload()).encode())
        raise OSError("no image")

    result = MovieClient(MovieStore(tmp_path), no_poster).lookup(MovieQuery("Test"), "key123")
    assert result.details.title == "Test movie" and not result.poster


def test_background_lookup_finishes_without_blocking_gui_and_closes():
    app = QApplication.instance() or QApplication([])
    requested, release = threading.Event(), threading.Event()

    class Client:
        from types import SimpleNamespace
        store = SimpleNamespace(epoch=0)

        def lookup(self, query, key, refresh, cache_epoch=None):
            requested.set()
            release.wait(3)
            return query.title

    worker = MovieWorker(Client())
    rows = []
    worker.finished.connect(lambda generation, result: rows.append((generation, result)))
    worker.submit(3, MovieQuery("One"), "key")
    assert requested.wait(1)
    worker.submit(4, MovieQuery("Two"), "key")
    worker.submit(5, MovieQuery("Three"), "key")
    release.set()
    deadline = time.monotonic() + 3
    while len(rows) < 2 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    worker.close()
    worker.thread.join(1)
    assert rows == [(3, "One"), (5, "Three")]
    assert not worker.thread.is_alive()
