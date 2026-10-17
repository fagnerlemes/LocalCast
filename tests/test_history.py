import os
import subprocess
import sys

import pytest

from localcast.history import (
    HistoryStore,
    PlaybackTracker,
    VideoIdentity,
    completed,
    resume_position,
)


def sample(position, serial=1, state='PLAYING', **changes):
    return dict(connected=True, matches_media=True, status_age_seconds=0,
                status_serial=serial, reported_position=position, player_state=state, **changes)


def test_identity_and_persistence(tmp_path):
    first, second = tmp_path / 'A/movie.mkv', tmp_path / 'B/movie.mkv'
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b'aaaa')
    second.write_bytes(b'aaaa')
    store = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(first)
    assert store.get(identity) is None
    store.save(identity, 4355, 7200, store.epoch)
    assert resume_position(HistoryStore(tmp_path / 'data').get(identity)) == 4355
    assert store.get(VideoIdentity.from_path(second)) is None
    moved = first.with_name('renamed.mkv')
    first.rename(moved)
    assert store.get(VideoIdentity.from_path(moved)) is None
    second.write_bytes(b'longer video')
    assert store.get(VideoIdentity.from_path(second)) is None


@pytest.mark.parametrize('position,duration,done', [
    (29, 7200, False), (6840, 7200, True), (6810, 7200, False),
    (1100, 1250, True), (30, 120, False), (114, 120, True),
    (29, 0, False), (100, 600, False),
])
def test_completion_rules(position, duration, done):
    assert completed(position, duration) == done


def test_tracker_confirmed_clock_pause_restart_and_clear(tmp_path, media_info):
    store = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(media_info.path)
    store.save(identity, 50, 120, store.epoch)
    tracker = PlaybackTracker(store, identity, 120, expected=50)
    tracker.observe(sample(0), now=0)
    assert store.get(identity)['position'] == 50
    tracker.observe(sample(50, 2), now=1)
    tracker.observe(sample(55, 3), now=5)
    assert store.get(identity)['position'] == 50
    tracker.observe(sample(56, 4, 'PAUSED'), now=6)
    assert store.get(identity)['position'] == 56
    tracker.observe(sample(90, 5, 'BUFFERING'), now=30)
    assert store.get(identity)['position'] == 56
    tracker.observe(sample(0, 6), now=31, force=True)
    assert store.get(identity)['position'] == 56
    # Explicit restart commits zero only after a new confirmed receiver sample.
    restarted = PlaybackTracker(store, identity, 120, expected=0, serial_floor=6)
    restarted.observe(sample(0, 7), now=40)
    assert resume_position(store.get(identity)) == 0
    store.clear()
    restarted.observe(sample(45, 8), now=60, force=True)
    assert store.count() == 0


@pytest.mark.parametrize('change', [
    {'connected': False}, {'matches_media': False}, {'status_age_seconds': 20},
    {'reported_position': float('nan')}, {'reported_position': -2}, {'status_serial': 0},
])
def test_invalid_samples_do_not_destroy_progress(change, tmp_path, media_info):
    store = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(media_info.path)
    store.save(identity, 50, 120, store.epoch)
    tracker = PlaybackTracker(store, identity, 120, expected=50)
    row = sample(50)
    row.update(change)
    tracker.observe(row, force=True)
    assert store.get(identity)['position'] == 50


def test_backward_seek_is_saved_and_finished_state(tmp_path, media_info):
    store = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(media_info.path)
    store.save(identity, 85, 120, store.epoch)
    tracker = PlaybackTracker(store, identity, 120, expected=40)
    tracker.observe(sample(40), now=0)
    assert store.get(identity)['position'] == 40
    tracker.observe(sample(0, 2, 'IDLE', idle_reason='FINISHED'), now=1)
    assert store.get(identity)['completed']
    assert resume_position(store.get(identity)) == 0


def test_committed_checkpoint_survives_abrupt_process_exit(tmp_path, media_info):
    data = tmp_path / 'data'
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join(sys.path)
    code = ('import os,sys; from localcast.history import HistoryStore,VideoIdentity; '
            's=HistoryStore(sys.argv[1]); s.save(VideoIdentity.from_path(sys.argv[2]),'
            '45,120,s.epoch); os._exit(7)')
    result = subprocess.run([sys.executable, '-B', '-c', code, str(data), str(media_info.path)], env=env)
    assert result.returncode == 7
    assert HistoryStore(data).get(VideoIdentity.from_path(media_info.path))['position'] == 45


def test_corrupt_database_does_not_prevent_playback_startup(tmp_path):
    (tmp_path / 'playback.db').write_bytes(b'not a database')
    store = HistoryStore(tmp_path)
    assert store.error and store.count() == 0
    assert (tmp_path / 'playback.db').read_bytes() == b'not a database'
