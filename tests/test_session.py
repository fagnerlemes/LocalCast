import http.client
from dataclasses import replace
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest

from localcast.cast_client import Device
from localcast.session import PlaybackSession


class FakeJob:
    jobs = []

    def __init__(self, info, root, offset, height, subtitle=None):
        self.directory = root / f"job-{len(self.jobs)}"
        self.directory.mkdir(parents=True)
        self.offset = offset
        self.closed = False
        self.info = info
        self.subtitle = subtitle
        self.jobs.append(self)

    def wait_ready(self):
        pass

    def snapshot(self):
        return {"encoded_seconds": 8, "speed": 2, "returncode": None}

    def close(self):
        self.closed = True


def test_hls_seek_restores_pause_and_source_position(media_info, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALCAST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("localcast.session.HlsJob", FakeJob)
    FakeJob.jobs = []
    client = Mock()
    client.snapshot.return_value = {"player_state": "PAUSED", "current_time": 3, "connected": True}
    session = PlaybackSession(0, client)
    # LAN-shaped URL only; Mock client never connects to this address.
    session.start(
        replace(media_info, path=media_info.path.with_suffix(".mkv")),
        Device("u", "TV", "192.168.1.50", "cast"),
        advertised_ip="192.168.1.10",
    )
    old_token = session.token
    first = session.job
    try:
        session.seek(75)
        assert first.closed and session.job.offset == 75
        assert session.token != old_token
        assert session.snapshot()["position"] == 78
        assert session.server.resolve([old_token, "master.m3u8"]) is None
        client.command.assert_any_call("pause")
    finally:
        session.close()
    assert all(job.closed for job in FakeJob.jobs)


def test_track_change_keeps_position_pause_and_selection_on_seek(track_info, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALCAST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("localcast.session.HlsJob", FakeJob)
    FakeJob.jobs = []
    client = Mock()
    client.snapshot.return_value = {"player_state": "PAUSED", "current_time": 3}
    session = PlaybackSession(0, client)
    session.start(
        track_info, Device("u", "TV", "192.168.1.50", "cast"), advertised_ip="192.168.1.10"
    )
    try:
        session.seek(50)
        old_token, old_job = session.token, session.job
        session.set_tracks(4, 7)
        assert old_job.closed and old_token != session.token
        assert session.job.offset == 53
        assert session.job.info.audio_index == 4
        assert session.job.subtitle.index == 7
        client.command.assert_any_call("pause")
        session.seek(80)
        assert session.job.subtitle.index == 7 and session.job.info.audio_index == 4
        session.set_tracks(-1, None)
        assert session.job.info.audio_index is None and session.job.subtitle is None
        before = session.job
        with pytest.raises(ValueError):
            session.set_tracks(400, None)
        with pytest.raises(ValueError):
            session.set_tracks(4, 9)
        assert session.job is before and not before.closed
    finally:
        session.close()


@pytest.mark.parametrize("quit_fails", [False, True])
def test_disconnect_after_stop_quits_receiver_and_releases_everything(media_info, quit_fails):
    client = Mock()
    client.snapshot.return_value = {}
    if quit_fails:
        client.quit_receiver.side_effect = TimeoutError("no response")
    session = PlaybackSession(0, client)
    session.start(
        media_info, Device("u", "TV", "192.168.1.50", "cast"), advertised_ip="192.168.1.10"
    )
    server = session.server
    session.stop()
    assert session.mode is None
    client.quit_receiver.assert_not_called()
    if quit_fails:
        with pytest.raises(RuntimeError, match="não confirmou"):
            session.disconnect()
    else:
        session.disconnect()
    client.quit_receiver.assert_called_once_with()
    client.close.assert_called_once_with()
    assert session.server is None and session.device is None and not server._thread.is_alive()
    session.close()
    client.quit_receiver.assert_called_once_with()


def test_window_close_quits_receiver_without_manual_stop(media_info):
    client = Mock()
    client.snapshot.return_value = {}
    session = PlaybackSession(0, client)
    session.start(
        media_info, Device("u", "TV", "192.168.1.50", "cast"), advertised_ip="192.168.1.10"
    )
    session.close()
    client.command.assert_called_once_with("stop")
    client.quit_receiver.assert_called_once_with()
    assert session.server is None


def test_failed_load_cleans_job_and_url(media_info, monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALCAST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("localcast.session.HlsJob", FakeJob)
    client = Mock()
    client.snapshot.return_value = {"player_state": "IDLE", "idle_reason": "ERROR"}
    client.load.side_effect = RuntimeError("LOAD_FAILED")
    session = PlaybackSession(0, client)
    try:
        with pytest.raises(RuntimeError, match="LOAD_FAILED"):
            session.start(
                media_info,
                Device("u", "TV", "192.168.1.50", "cast"),
                force_hls=True,
                advertised_ip="192.168.1.10",
            )
        assert session.mode is None and session.job is None and session.token is None
        assert session.last_failure["message"] == "LOAD_FAILED"
        assert session.last_failure["session"]["mode"] == "hls"
        assert FakeJob.jobs[-1].closed
    finally:
        session.close()


@pytest.mark.parametrize("extension,mime", [(".mp4", "video/mp4"), (".mkv", "video/x-matroska")])
def test_original_serves_unchanged_bytes_without_encoder(track_info, monkeypatch, extension, mime):
    path = track_info.path.with_suffix(extension)
    body = b"original container and codec bytes: " + bytes(range(256)) * 20
    path.write_bytes(body)
    info = replace(track_info, path=path, video_codec="hevc", width=3840, height=2160)
    assert not info.direct_ok
    encoder = Mock(side_effect=AssertionError("Original must never encode"))
    monkeypatch.setattr("localcast.session.HlsJob", encoder)
    client = Mock()
    client.snapshot.return_value = {}
    session = PlaybackSession(0, client)
    session.start(
        info,
        Device("u", "TV", "192.168.1.50", "cast"),
        force_hls=True,
        advertised_ip="192.168.1.10",
        original=True,
        audio_index=4,
        subtitle_index=6,
    )
    try:
        assert session.mode == "original" and session.job is None
        assert session.info is info and session.subtitle is None
        client.load.assert_called_once_with(session.url, mime, path.name, hls=False)
        assert session.url.endswith("media" + extension)
        connection = http.client.HTTPConnection("127.0.0.1", session.server.port, timeout=5)
        try:
            connection.request("GET", urlsplit(session.url).path, headers={"Range": "bytes=8-49"})
            response = connection.getresponse()
            assert response.status == 206 and response.read() == body[8:50]
            assert response.getheader("Content-Type") == mime
            connection.request("GET", urlsplit(session.url).path)
            response = connection.getresponse()
            assert response.status == 200 and response.read() == body
        finally:
            connection.close()
        token = session.token
        session.seek(50)
        client.command.assert_called_with("seek", 50)
        assert session.token == token
        with pytest.raises(ValueError, match="Original"):
            session.set_tracks(4, 6)
        assert session.token == token
        encoder.assert_not_called()
    finally:
        session.close()


def test_original_rejection_does_not_fallback_to_conversion(track_info, monkeypatch):
    encoder = Mock()
    monkeypatch.setattr("localcast.session.HlsJob", encoder)
    client = Mock()
    client.snapshot.return_value = {"idle_reason": "ERROR"}
    client.load.side_effect = RuntimeError("LOAD_FAILED")
    session = PlaybackSession(0, client)
    try:
        with pytest.raises(RuntimeError, match="LOAD_FAILED"):
            session.start(
                track_info,
                Device("u", "TV", "192.168.1.50", "cast"),
                advertised_ip="192.168.1.10",
                original=True,
            )
        assert session.last_failure["session"]["mode"] == "original"
        encoder.assert_not_called()
    finally:
        session.close()
