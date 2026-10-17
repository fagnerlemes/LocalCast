import array
import cmath
import math
import os
import subprocess

import pytest
from track_samples import make_track_sample

from localcast.media import probe
from localcast.paths import process_options
from localcast.transcoder import HlsJob


def frame(ffmpeg, file, time):
    output = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-v",
            "error",
            "-i",
            str(file),
            "-ss",
            str(time),
            "-frames:v",
            "1",
            "-an",
            "-pix_fmt",
            "gray",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
        timeout=30,
        **process_options(),
    )
    return output.stdout


@pytest.mark.integration
@pytest.mark.parametrize("subtitle_ordinal", [0, 1, 2])
@pytest.mark.parametrize("encoder_mode", ["cpu", "auto"])
def test_selected_audio_embedded_subtitle_and_seek(tools, tmp_path, subtitle_ordinal, encoder_mode):
    if encoder_mode == "auto" and os.environ.get("LOCALCAST_TEST_GPU") != "1":
        pytest.skip("GPU test explicitly enabled only on hardware test machine")
    ffmpeg, ffprobe = tools
    movie = make_track_sample(ffmpeg, tmp_path / "sample")
    info = probe(movie, ffprobe)
    assert [track.language for track in info.audio_tracks] == ["por", "eng"]
    assert [track.codec for track in info.subtitle_tracks] == ["subrip", "ass", "hdmv_pgs_subtitle"]
    selected = info.with_audio(info.audio_tracks[1].index)
    subtitle = info.subtitle_tracks[subtitle_ordinal]
    for start in (0, 3, 6):
        job = HlsJob(selected, tmp_path / "cache", start=start, ffmpeg=ffmpeg, subtitle=subtitle,
                     encoder_mode=encoder_mode)
        try:
            job.wait_ready()
            job.wait_finished()
            assert job.process.returncode == 0, job.snapshot()
            if encoder_mode == "auto":
                assert job.snapshot()["hardware"], job.snapshot()
            playlist = job.directory / "stream.m3u8"
            # Preserve cue timing, including seeking into a caption already on screen.
            before = frame(ffmpeg, playlist, 0.2)
            during = frame(ffmpeg, playlist, {0: 3, 3: 0.6, 6: 2}[start])
            after = frame(ffmpeg, playlist, {0: 4.5, 3: 1.5, 6: 3.5}[start])
            assert before and (max(before) > 150 if start == 3 else max(before) < 30)
            assert during and max(during) > 150
            assert after and max(after) < 30
            audio = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-v",
                    "error",
                    "-i",
                    str(playlist),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "8000",
                    "-t",
                    "2",
                    "-f",
                    "f32le",
                    "-",
                ],
                capture_output=True,
                check=True,
                timeout=30,
                **process_options(),
            ).stdout
            wave = array.array("f", audio)[2000:8000]

            def energy(frequency):
                return abs(
                    sum(
                        value * cmath.exp(-2j * math.pi * frequency * n / 8000)
                        for n, value in enumerate(wave)
                    )
                )

            assert energy(880) > 10 * energy(220)
        finally:
            job.close()
