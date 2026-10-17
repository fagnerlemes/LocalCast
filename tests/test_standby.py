"""Standby lifecycle and LAN transport, using a fake receiver; never connects to a TV."""

import http.client
from unittest.mock import Mock
from urllib.parse import urlsplit

import pytest

from localcast.cast_client import Device
from localcast.media import probe
from localcast.session import PlaybackSession
from localcast.ui_assets import asset_path

DEVICE = Device("standby-tv", "TV de teste", "192.168.1.50", "cast")


def client_mock():
    client = Mock()
    client.snapshot.return_value = {"connected": True, "player_state": "PAUSED", "current_time": 0}
    return client


def test_standby_transport_movie_transition_stop_and_disconnect(media_info, monkeypatch):
    encoder = Mock(side_effect=AssertionError("Standby must not start an encoder"))
    monkeypatch.setattr("localcast.session.HlsJob", encoder)
    client = client_mock()
    session = PlaybackSession(0, client)
    try:
        session.show_standby(DEVICE, "192.168.1.10")
        snapshot = session.snapshot()
        assert snapshot["standby_active"] and snapshot["mode"] is None
        assert snapshot["total_duration"] == 0 and session.info is None
        url = urlsplit(session.url)
        token = session.token
        assert url.hostname == "192.168.1.10" and url.path.endswith("/media.jpg")
        client.load.assert_called_once_with(session.url, "image/jpeg", "LocalCast • By Fagner Lemes", image=True)
        client.command.assert_not_called()
        connection = http.client.HTTPConnection("127.0.0.1", session.server.port, timeout=5)
        try:
            connection.request("GET", url.path, headers={"Range": "bytes=0-63"})
            response = connection.getresponse()
            assert response.status == 206 and response.getheader("Content-Type") == "image/jpeg"
            assert response.read() == asset_path("localcast-espera-1280x720.jpg").read_bytes()[:64]
        finally:
            connection.close()
        session.start(media_info, DEVICE, advertised_ip="192.168.1.10")
        assert session.mode == "direct" and not session.standby_active
        assert session.server.resolve([token, "media.mp4"]) is None
        assert client.load.call_args.args[2] == media_info.path.name
        session.stop_to_standby()
        assert session.mode is None and session.standby_active and session.job is None
        assert session.standby_format == 'image'
        encoder.assert_not_called()
        server = session.server
        session.disconnect()
        assert not session.standby_active and session.server is None
        assert not server._thread.is_alive()
        client.quit_receiver.assert_called_once_with()
    finally:
        session.close()


@pytest.mark.parametrize("failed_command", ["load", "pause"])
def test_failed_standby_releases_media_and_can_disconnect(failed_command):
    client = client_mock()
    if failed_command == "load":
        client.load.side_effect = RuntimeError("standby load rejected")
    else:
        client.load.side_effect = lambda *args, **kwargs: (
            (_ for _ in ()).throw(RuntimeError('photo rejected')) if kwargs.get('image') else None)
        client.command.side_effect = lambda name: (
            (_ for _ in ()).throw(RuntimeError("pause not confirmed")) if name == "pause" else None
        )
    session = PlaybackSession(0, client)
    try:
        with pytest.raises(RuntimeError):
            session.show_standby(DEVICE, "192.168.1.10")
        assert not session.standby_active and session.token is None and session.url is None
        assert session.last_failure["session"]["standby_active"]
        assert not session.server._resources
    finally:
        session.close()
    client.quit_receiver.assert_called_once_with()


def test_missing_standby_does_not_interrupt_active_movie(media_info, tmp_path, monkeypatch):
    client = client_mock()
    session = PlaybackSession(0, client)
    try:
        session.start(media_info, DEVICE, advertised_ip="192.168.1.10")
        original_token = session.token
        monkeypatch.setattr("localcast.session.asset_path", lambda name: tmp_path / name)
        with pytest.raises(FileNotFoundError, match="Tela de espera"):
            session.show_standby(DEVICE, "192.168.1.10")
        assert session.mode == "direct" and session.token == original_token
        client.command.assert_not_called()
    finally:
        session.close()


def test_packaged_standby_is_silent_compatible_h264(tools):
    info = probe(asset_path("localcast-espera.mp4"), tools[1])
    assert info.video_codec == "h264" and info.level == 31
    assert (info.width, info.height) == (1280, 720) and info.fps == 1
    assert info.pixel_format == "yuv420p" and not info.audio_tracks
    assert info.duration >= 30 and info.direct_ok


def test_stop_without_initial_standby_reconnects_and_loads_image(media_info):
    client = client_mock()
    session = PlaybackSession(0, client)
    try:
        session.start(media_info, DEVICE, advertised_ip='192.168.1.10')
        client.snapshot.return_value['connected'] = False  # Transient status after STOP.
        client.command.reset_mock()
        session.stop_to_standby()
        assert session.standby_format == 'image' and session.standby_active
        assert client.connect.call_count == 2
        client.command.assert_called_once_with('stop')
        assert client.load.call_args.kwargs['image']
    finally:
        session.close()


def test_photo_rejection_falls_back_without_starting_encoder():
    client = client_mock()
    def load(url, mime, title, **kwargs):
        if mime == 'image/jpeg':
            raise RuntimeError('photo unsupported')
    client.load.side_effect = load
    session = PlaybackSession(0, client)
    try:
        session.show_standby(DEVICE, '192.168.1.10')
        assert session.standby_format == 'video-fallback' and session.job is None
        assert len(session.server._resources) == 1
        client.command.assert_called_once_with('pause')
    finally:
        session.close()
