import json
import subprocess
from urllib.request import urlopen

import pytest

from localcast.http_server import MediaServer
from localcast.media import probe
from localcast.paths import process_options
from localcast.transcoder import HlsJob


def run(command):
    return subprocess.run(
        command, check=True, capture_output=True, timeout=120, **process_options()
    )


@pytest.mark.integration
@pytest.mark.parametrize("kind", ["mp4", "mkv-hevc", "mkv-4k", "mkv-hdr"])
def test_real_ffmpeg_hls_output(tools, tmp_path, kind):
    ffmpeg, ffprobe = tools
    hevc = kind != "mp4"
    size = "3840x2160" if kind == "mkv-4k" else "640x360"
    source = tmp_path / ("entrada vídeo.mkv" if hevc else "entrada vídeo.mp4")
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={size}:rate=24",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=5.1:sample_rate=48000" if hevc else "sine=sample_rate=48000",
        "-t",
        "9",
        "-c:v",
        "libx265" if hevc else "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "eac3" if hevc else "aac",
    ]
    if hevc:
        command += ["-x265-params", "log-level=error"]
    if kind == "mkv-hdr":
        command += [
            "-pix_fmt",
            "yuv420p10le",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "smpte2084",
            "-colorspace",
            "bt2020nc",
        ]
    if not hevc:
        command += ["-ac", "2", "-movflags", "+faststart"]
    run(command + [str(source)])
    info = probe(source, ffprobe)
    if hevc:
        assert info.video_codec == "hevc" and info.audio_codec == "eac3" and info.channels == 6
        assert not info.direct_ok
    job = HlsJob(info, tmp_path / "cache", ffmpeg=ffmpeg)
    server = MediaServer("127.0.0.1", 0)
    directory = job.directory
    try:
        job.wait_ready(timeout=90)
        job.wait_finished(timeout=90)
        assert job.process.returncode == 0, job.snapshot()
        playlist = (directory / "stream.m3u8").read_text()
        assert "#EXT-X-PLAYLIST-TYPE:EVENT" in playlist and "#EXT-X-ENDLIST" in playlist
        segments = [line for line in playlist.splitlines() if line.endswith(".ts")]
        assert len(segments) >= 2 and not list(directory.glob("*.tmp"))
        token = server.register_hls(directory)
        with urlopen(server.url(token, "127.0.0.1", "master.m3u8")) as response:
            assert b'CODECS="avc1.640029,mp4a.40.2"' in response.read()
        with urlopen(server.url(token, "127.0.0.1", segments[0])) as response:
            assert response.headers["Content-Type"] == "video/mp2t" and len(response.read()) > 1000
        raw = json.loads(
            run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_streams",
                    "-of",
                    "json",
                    str(directory / segments[0]),
                ]
            ).stdout
        )
        video = next(s for s in raw["streams"] if s["codec_type"] == "video")
        audio = next(s for s in raw["streams"] if s["codec_type"] == "audio")
        assert (
            video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p" and video["level"] <= 41
        )
        assert video["width"] <= 1920 and video["height"] <= 1080
        assert (
            audio["codec_name"] == "aac"
            and audio["channels"] == 2
            and audio["sample_rate"] == "48000"
        )
        # Decode all generated segments to catch timestamp/concatenation failures.
        run(
            [
                ffmpeg,
                "-hide_banner",
                "-v",
                "error",
                "-i",
                str(directory / "stream.m3u8"),
                "-f",
                "null",
                "-",
            ]
        )
    finally:
        server.close()
        job.close()
    assert not directory.exists()
