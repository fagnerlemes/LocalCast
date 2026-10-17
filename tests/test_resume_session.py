
import pytest

from localcast.cast_client import Device
from localcast.history import HistoryStore, VideoIdentity
from localcast.session import PlaybackSession


class Receiver:
    def __init__(self):
        self.status = {'status_serial': 0}
        self.loads = []
        self.reject = False
        self.cast = None

    def connect(self, uuid):
        pass

    def load(self, url, mime, title, **options):
        self.loads.append((url, options))
        self.status = {'status_serial': self.status['status_serial'] + 1,
                       'status_age_seconds': 0, 'content_id': url, 'connected': True,
                       'current_time': options.get('current_time', 0),
                       'player_state': 'PLAYING'}
        if self.reject:
            self.status['content_id'] = 'other-video'
            raise RuntimeError('LOAD_FAILED')

    def reported_snapshot(self):
        return dict(self.status)

    snapshot = reported_snapshot

    def command(self, action, position=None):
        if action == 'stop':
            self.status.update(player_state='IDLE', idle_reason='CANCELLED', current_time=0)
        elif action == 'pause':
            self.status['player_state'] = 'PAUSED'
        elif action == 'seek':
            self.status['current_time'] = position
        self.status['status_serial'] += 1

    def request_status(self):
        pass

    def quit_receiver(self):
        pass

    def close(self):
        pass


@pytest.mark.parametrize('mode', ['direct', 'original', 'hls'])
def test_resume_starts_at_correct_source_offset_and_survives_stop(
    tmp_path, monkeypatch, media_info, mode,
):
    from test_session import FakeJob
    monkeypatch.setenv('LOCALCAST_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('localcast.session.HlsJob', FakeJob)
    FakeJob.jobs = []
    history = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(media_info.path)
    history.save(identity, 50, 120, history.epoch)
    receiver = Receiver()
    session = PlaybackSession(0, receiver, history)
    try:
        session.start(media_info, Device('u', 'Simulated', '192.168.1.5', 'cast'),
                      force_hls=mode == 'hls', original=mode == 'original',
                      advertised_ip='192.168.1.10', start_position=50)
        assert session.mode == mode
        assert receiver.loads[-1][1].get('current_time', 0) == (0 if mode == 'hls' else 50)
        if mode == 'hls':
            assert session.job.offset == 50
        receiver.status['current_time'] += 7
        receiver.status['status_serial'] += 1
        session.command('pause')
        session.stop()
        assert history.get(identity)['position'] == 57
        session.start(media_info, Device('u', 'Simulated', '192.168.1.5', 'cast'),
                      advertised_ip='192.168.1.10', start_position=0)
        assert history.get(identity)['position'] == 0
    finally:
        session.close()


def test_failed_resume_and_other_content_preserve_saved_point(tmp_path, media_info):
    history = HistoryStore(tmp_path / 'data')
    identity = VideoIdentity.from_path(media_info.path)
    history.save(identity, 50, 120, 0)
    receiver = Receiver()
    receiver.reject = True
    session = PlaybackSession(0, receiver, history)
    try:
        with pytest.raises(RuntimeError, match='LOAD_FAILED'):
            session.start(media_info, Device('u', 'Test', '192.168.1.5', 'cast'),
                          advertised_ip='192.168.1.10', start_position=50)
        assert history.get(identity)['position'] == 50
        assert session.mode is None and session.tracker is None
    finally:
        session.close()
