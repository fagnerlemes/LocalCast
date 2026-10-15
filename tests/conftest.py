from dataclasses import replace

import pytest

from localcast.media import AudioTrack, SubtitleTrack, parse_probe


@pytest.fixture
def media_info(tmp_path):
    path = tmp_path / "vídeo com espaço.mp4"
    path.write_bytes(b"0123456789")
    return parse_probe(
        path,
        {
            "format": {"duration": "120", "bit_rate": "5000000"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "profile": "High",
                    "level": 41,
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                    "pix_fmt": "yuv420p",
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "profile": "LC",
                    "channels": 2,
                    "sample_rate": "48000",
                },
            ],
        },
    )


@pytest.fixture
def track_info(media_info):
    return replace(
        media_info,
        path=media_info.path.with_suffix(".mkv"),
        audio_tracks=(
            AudioTrack(1, "aac", "por", "Dublado", True, 2, 48000, "LC"),
            AudioTrack(4, "eac3", "eng", "Original", False, 6, 48000),
        ),
        subtitle_tracks=(
            SubtitleTrack(6, 0, "subrip", "por", "Completa", False, False),
            SubtitleTrack(7, 1, "hdmv_pgs_subtitle", "eng", "", False, True),
            SubtitleTrack(9, 2, "unknown", "und", "", False, False),
        ),
    )


@pytest.fixture
def tools():
    from localcast.paths import tool_path

    try:
        return tool_path("ffmpeg"), tool_path("ffprobe")
    except FileNotFoundError:
        pytest.skip("ffmpeg/ffprobe ausentes: teste de integração não executado")
