from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from localcast.cast_client import CastClient, _Listener


def test_load_uses_default_receiver_contract_and_waits_for_status():
    client = CastClient()
    controller = Mock()
    cast = SimpleNamespace(
        media_controller=controller,
        socket_client=SimpleNamespace(is_connected=True),
        app_id="CC1AD845",
    )
    client.cast = cast
    listener = _Listener(client, cast)

    def acknowledge(url, mime, **kwargs):
        listener.new_media_status(
            SimpleNamespace(content_id=url, player_state="PLAYING", current_time=0)
        )

    controller.play_media.side_effect = acknowledge
    client.load(
        "http://192.168.1.10/test/master.m3u8", "application/vnd.apple.mpegurl", "teste", True
    )
    assert controller.play_media.call_args.kwargs["stream_type"] == "LIVE"
    assert controller.play_media.call_args.kwargs["current_time"] == 0
    client.load("http://192.168.1.10/test/media.mp4", "video/mp4", "teste")
    assert controller.play_media.call_args.kwargs["stream_type"] == "BUFFERED"
    client.load("http://192.168.1.10/test/media.mp4", "video/mp4", "teste", current_time=52)
    assert controller.play_media.call_args.kwargs["current_time"] == 52
    for hls in (False, True):
        client.load('http://192.168.1.10/video', 'video/mp4', 'Filme identificado', hls=hls,
                    cover_url='http://192.168.1.10/art/cover', duration=8700)
        options = controller.play_media.call_args.kwargs
        assert options['metadata'] == {
            'metadataType': 1, 'title': 'Filme identificado',
            'images': [{'url': 'http://192.168.1.10/art/cover'}],
            'subtitle': 'Duração total: 02:25:00',
        }
        assert options['stream_type'] == ('LIVE' if hls else 'BUFFERED')
        assert options.get('media_info') == (None if hls else {'duration': 8700})


def test_load_error_surfaces_and_stale_listener_is_ignored():
    client = CastClient()
    cast = SimpleNamespace(
        media_controller=Mock(), socket_client=SimpleNamespace(is_connected=True), app_id="CC1AD845"
    )
    client.cast = cast
    listener = _Listener(client, cast)
    cast.media_controller.play_media.side_effect = lambda *a, **k: listener.load_media_failed(
        0, 104
    )
    with pytest.raises(RuntimeError, match="104"):
        client.load("http://192.168.1.10/video", "video/mp4", "teste")
    client.disconnect()
    listener.load_media_failed(0, 999)
    assert client.snapshot()["load_error"] is None


@pytest.mark.parametrize(
    "app_id,owned,expected",
    [("CC1AD845", True, True), ("CC1AD845", False, False), ("OTHER", True, False)],
)
def test_quit_receiver_only_stops_owned_default_application(app_id, owned, expected):
    client = CastClient()
    client.cast = SimpleNamespace(
        app_id=app_id, socket_client=SimpleNamespace(is_connected=True), quit_app=Mock()
    )
    client._owns_receiver = owned
    client.quit_receiver()
    if expected:
        client.cast.quit_app.assert_called_once_with(timeout=10)
    else:
        client.cast.quit_app.assert_not_called()
    assert not client._owns_receiver


def test_quit_receiver_reports_network_failure():
    client = CastClient()
    client.cast = SimpleNamespace(
        app_id="CC1AD845", socket_client=SimpleNamespace(is_connected=False), quit_app=Mock()
    )
    client._owns_receiver = True
    with pytest.raises(ConnectionError):
        client.quit_receiver()
    client.cast.quit_app.assert_not_called()


def test_device_volume_and_stale_target_protection():
    client = CastClient()
    cast = SimpleNamespace(status=SimpleNamespace(volume_level=.42, volume_muted=True),
                           socket_client=SimpleNamespace(is_connected=True), app_id='CC1AD845',
                           set_volume=Mock(), set_volume_muted=Mock())
    client.cast = cast
    assert client.snapshot()['volume_level'] == .42
    assert client.snapshot()['volume_muted']
    client.set_volume(25, cast)
    cast.set_volume.assert_called_once_with(.25, timeout=5)
    cast.set_volume_muted.assert_called_once_with(False, timeout=5)
    for value in (-1, 101, float('nan')):
        with pytest.raises(ValueError):
            client.set_volume(value, cast)
    client.cast = None
    with pytest.raises(ConnectionError):
        client.set_volume(80, cast)
    assert client.snapshot()['volume_level'] is None
    assert cast.set_volume.call_count == 1


def test_photo_uses_none_stream_type_and_accepts_idle_without_error():
    client = CastClient()
    cast = SimpleNamespace(media_controller=Mock(),
                           socket_client=SimpleNamespace(is_connected=True), app_id='CC1AD845')
    client.cast = cast
    listener = _Listener(client, cast)
    cast.media_controller.play_media.side_effect = lambda url, mime, **kwargs: listener.new_media_status(
        SimpleNamespace(content_id=url, player_state='IDLE', current_time=0))
    client.load('http://192.168.1.10/art.jpg', 'image/jpeg', 'LocalCast', image=True)
    options = cast.media_controller.play_media.call_args.kwargs
    assert options['stream_type'] == 'NONE' and options['metadata']['metadataType'] == 4
