from unittest.mock import Mock

import pytest

from localcast.buffer_budget import BufferBudget
from localcast.encoders import CPU, encoder_plans
from localcast.session import PlaybackSession


def test_reserve_uses_playback_watermarks_and_pause():
    budget = BufferBudget(90)
    assert not budget.decide(88, 0, "PREPARING")
    assert budget.decide(92, 0, "PREPARING")
    assert budget.decide(92, 0, "PAUSED")
    assert budget.decide(92, 40, "PLAYING")
    assert not budget.decide(92, 48, "PLAYING")
    assert not budget.decide(100, 48, "PLAYING")
    assert budget.decide(140, 48, "PLAYING")


@pytest.mark.parametrize("position,state", [(None, "PLAYING"), (0, "UNKNOWN"), (float('nan'), "PLAYING")])
def test_lost_clock_does_not_freeze_encoder(position, state):
    budget = BufferBudget(90, suspended=True)
    assert not budget.decide(100, position, state)


def test_short_end_is_allowed_to_finish_and_invalid_reserve_is_rejected():
    assert not BufferBudget(30).decide(32, 0, "PAUSED", finishing=True)
    for target in (0, 12, 301, float('inf')):
        with pytest.raises(ValueError):
            BufferBudget(target)


def test_unavailable_hardware_and_explicit_cpu_keep_software_path(media_info, monkeypatch):
    monkeypatch.setattr('localcast.encoders.available_encoders', lambda _: frozenset())
    assert encoder_plans('ffmpeg', 'auto', media_info) == [CPU]
    assert encoder_plans('ffmpeg', 'cpu', media_info) == [CPU]


def test_receiver_clock_rejects_old_content_and_stale_or_disconnected_status():
    client = Mock()
    session = PlaybackSession(0, client)
    session.url = 'http://example.test/new-session'
    client.snapshot.return_value = dict(connected=True, content_id='old-session', current_time=70)
    assert session._hls_clock() == {'position': 0.0, 'state': 'PREPARING'}
    client.snapshot.return_value = dict(connected=True, content_id=session.url, current_time=8,
                                        player_state='PLAYING', status_age_seconds=0)
    assert session._hls_clock() == {'position': 8, 'state': 'PLAYING'}
    client.snapshot.return_value['status_age_seconds'] = 20
    assert session._hls_clock()['position'] is None
    client.snapshot.return_value['connected'] = False
    assert session._hls_clock()['state'] == 'UNKNOWN'
    client.request_status.assert_called_once()
