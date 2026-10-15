from dataclasses import replace

import pytest

from localcast.media import parse_probe
from localcast.transcoder import build_command


def test_direct_and_mkv_policy(media_info):
    assert media_info.direct_ok
    assert not replace(media_info, path=media_info.path.with_suffix(".mkv")).direct_ok


@pytest.mark.parametrize(
    "changes",
    [
        {"video_codec": "hevc", "width": 3840, "height": 2160},
        {"pixel_format": "yuv420p10le"},
        {"audio_codec": "eac3", "channels": 6},
        {"fps": 60},
        {"level": 51},
        {"profile": "High 10"},
        {"hdr": True},
        {"channels": 6},
        {"sample_rate": 96000},
        {"bit_rate": 30000000},
    ],
)
def test_incompatible_inputs_require_conversion(media_info, changes):
    assert not replace(media_info, **changes).direct_ok


def test_probe_ignores_cover_and_chooses_default_audio(tmp_path):
    result = parse_probe(
        tmp_path / "movie.mkv",
        {
            "format": {"duration": "N/A"},
            "streams": [
                {"index": 0, "codec_type": "video", "disposition": {"attached_pic": 1}},
                {
                    "index": 1,
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "avg_frame_rate": "0/0",
                    "r_frame_rate": "24/1",
                    "duration": "14",
                    "color_transfer": "smpte2084",
                },
                {"index": 2, "codec_type": "audio", "codec_name": "aac"},
                {
                    "index": 3,
                    "codec_type": "audio",
                    "codec_name": "eac3",
                    "disposition": {"default": 1},
                },
            ],
        },
    )
    assert result.video_index == 1 and result.audio_index == 3
    assert result.fps == 24 and result.duration == 14 and result.hdr


def test_transcode_contract_and_seek_input(media_info, tmp_path):
    info = replace(
        media_info,
        video_codec="hevc",
        audio_codec="eac3",
        channels=6,
        width=3840,
        height=2160,
        fps=60,
    )
    cmd = build_command(info, tmp_path, start=75, ffmpeg="ffmpeg")
    assert cmd.index("-ss") < cmd.index("-i")
    for flag, value in [
        ("-c:v", "libx264"),
        ("-level:v", "4.1"),
        ("-r", "30.000000"),
        ("-c:a", "aac"),
        ("-ac", "2"),
        ("-ar", "48000"),
        ("-hls_segment_type", "mpegts"),
        ("-hls_playlist_type", "event"),
    ]:
        assert cmd[cmd.index(flag) + 1] == value
    assert "independent_segments+temp_file" in cmd
    assert str(info.path) in cmd  # Unicode and spaces remain one subprocess argument.


def test_hdr_filter_and_invalid_seek(media_info, tmp_path):
    cmd = build_command(replace(media_info, hdr=True), tmp_path, ffmpeg="ffmpeg")
    assert "tonemap=" in cmd[cmd.index("-vf") + 1]
    with pytest.raises(ValueError):
        build_command(media_info, tmp_path, start=120, ffmpeg="ffmpeg")


def test_track_metadata_uses_global_indexes_and_subtitle_ordinals(track_info):
    selected = track_info.with_audio(4)
    assert selected.audio_codec == "eac3" and selected.channels == 6
    assert "Português" in track_info.audio_tracks[0].label
    assert track_info.subtitle_track(7).ordinal == 1
    assert track_info.subtitle_track(7).kind == "bitmap"
    assert "forçada" in track_info.subtitle_track(7).label
    assert track_info.with_audio(None).audio_codec is None
    assert not replace(track_info, path=track_info.path.with_suffix(".mp4")).direct_ok
    with pytest.raises(ValueError):
        track_info.with_audio(6)


def test_subtitle_commands_map_selected_audio_and_preserve_timeline(track_info, tmp_path):
    cmd = build_command(
        track_info.with_audio(4),
        tmp_path,
        start=50,
        ffmpeg="ffmpeg",
        subtitle=track_info.subtitle_track(6),
    )
    assert "0:4" in cmd
    assert "setpts=PTS+50.000000/TB" in cmd[cmd.index("-vf") + 1]
    cmd = build_command(
        track_info, tmp_path, ffmpeg="ffmpeg", subtitle=track_info.subtitle_track(7)
    )
    assert "[0:0][0:7]overlay" in cmd[cmd.index("-filter_complex") + 1]
    assert "[vout]" in cmd
