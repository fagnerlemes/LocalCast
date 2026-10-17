import json
import os
import threading
from types import SimpleNamespace

import pytest

from localcast.history import HistoryStore, VideoIdentity
from localcast.movie_info import MovieClient, MovieQuery, MovieStore
from localcast.storage import StorageManager, mark_session


def manager(tmp_path):
    root = tmp_path / 'data'
    root.mkdir()
    return StorageManager(root, HistoryStore(root), MovieStore(root),
                          SimpleNamespace(_lock=threading.RLock(), mode=None, standby_active=False))


def test_clean_preserves_active_external_and_unknown_files(tmp_path):
    storage = manager(tmp_path)
    cache = storage.root / 'cache'
    active, old = cache / 'session-active', cache / 'session-old'
    for directory in (active, old):
        directory.mkdir(parents=True)
        (directory / 'segment_000001.ts').write_bytes(b'segment')
    mark_session(active)
    mark_session(old, closed=True)
    (old / 'personal-video.mkv').write_bytes(b'user')
    unknown = cache / 'session-legacy'
    unknown.mkdir()
    (unknown / 'segment_000001.ts').write_bytes(b'unknown owner')
    logs = storage.root / 'logs'
    logs.mkdir()
    (logs / 'localcast.log').write_text('open')
    (logs / 'localcast.log.1').write_text('old')
    (logs / 'my-note.txt').write_text('user')
    storage.clean('logs')
    assert (logs / 'localcast.log').read_text() == 'open'
    assert not (logs / 'localcast.log.1').exists()
    storage.clean('cache')
    assert (active / 'segment_000001.ts').exists()
    assert not (old / 'segment_000001.ts').exists()
    assert (old / 'personal-video.mkv').read_bytes() == b'user'
    assert (old / '.owner.json').exists()
    assert (unknown / 'segment_000001.ts').exists()


def test_clear_history_and_reset_preserve_original(tmp_path, media_info, monkeypatch):
    storage = manager(tmp_path)
    monkeypatch.setenv('LOCALCAST_DATA_DIR', str(storage.root))
    identity = VideoIdentity.from_path(media_info.path)
    storage.history.save(identity, 45, 120, 0)
    storage.movies.save_settings('test-key', False)
    storage.session.mode = 'hls'
    with pytest.raises(RuntimeError):
        storage.clean('history')
    with pytest.raises(RuntimeError):
        storage.clean('reset')
    assert storage.history.count() == 1
    storage.session.mode = None
    storage.clean('history')
    assert storage.history.count() == 0 and storage.movies.settings()['key'] == 'test-key'
    storage.clean('reset')
    assert storage.movies.settings() == {'key': '', 'automatic': True}
    assert media_info.path.read_bytes() == b'0123456789'
    from localcast.diagnostics import close_logging
    close_logging()


def test_late_movie_response_cannot_recreate_cache(tmp_path):
    storage = manager(tmp_path)
    client = MovieClient(storage.movies)
    started, proceed = threading.Event(), threading.Event()
    def fetch(url, limit):
        started.set()
        assert proceed.wait(3)
        return json.dumps({'Title': 'Test', 'Response': 'True', 'Poster': 'N/A'}).encode()
    client._get = fetch
    thread = threading.Thread(target=client.lookup, args=(MovieQuery('Test'), 'test-key'))
    thread.start()
    assert started.wait(3)
    storage.clean('cache')
    proceed.set()
    thread.join(3)
    assert not storage.movies.cache.exists()
    # An older queued request is equally forbidden from writing after the reset.
    client.lookup(MovieQuery('Other'), 'test-key', cache_epoch=0)
    assert not storage.movies.cache.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction safety')
def test_junction_and_external_files_are_not_followed(tmp_path):
    storage = manager(tmp_path)
    outside = tmp_path / 'external'
    outside.mkdir()
    (outside / 'localcast.log.1').write_text('outside')
    link = storage.root / 'logs'
    # Use Python's cmd-free junction helper shipped with CPython on Windows.
    import _winapi
    _winapi.CreateJunction(str(outside), str(link))
    try:
        with pytest.raises(ValueError):
            storage.clean('logs')
        assert (outside / 'localcast.log.1').read_text() == 'outside'
    finally:
        link.rmdir()  # Removes only this junction, not its target.
