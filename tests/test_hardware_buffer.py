"""Real synthetic HLS and owned-process suspension; never Cast discovery or LOAD."""

import os
import subprocess
import time

import psutil
import pytest

from localcast.encoders import CPU, EncoderPlan
from localcast.media import probe
from localcast.paths import process_options
from localcast.transcoder import HlsJob


def make_source(ffmpeg, target, seconds=3):
    subprocess.run([
        ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y', '-f', 'lavfi',
        '-i', 'color=c=black:s=640x360:r=24', '-f', 'lavfi', '-i', 'sine=sample_rate=48000',
        '-t', str(seconds), '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ac', '2', str(target),
    ], check=True, capture_output=True, timeout=60, **process_options())


def until(predicate, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError('Timed out waiting for actual FFmpeg state')


@pytest.mark.integration
def test_failed_hardware_start_rebuilds_hls_on_cpu(tools, tmp_path, monkeypatch):
    ffmpeg, ffprobe = tools
    source = tmp_path / 'source.mkv'
    make_source(ffmpeg, source)
    monkeypatch.setattr('localcast.transcoder.encoder_plans', lambda *args: [
        EncoderPlan('localcast_missing_encoder', 'GPU intentionally unavailable'), CPU,
    ])
    job = HlsJob(probe(source, ffprobe), tmp_path / 'cache', ffmpeg=ffmpeg, encoder_mode='auto')
    try:
        job.wait_ready()
        job.wait_finished()
        state = job.snapshot()
        assert not state['hardware'] and state['encoder'] == 'CPU x264'
        assert len(state['fallbacks']) == 1 and state['fallbacks'][0]['reason']
        assert job.process.returncode == 0
        subprocess.run([ffmpeg, '-v', 'error', '-i', str(job.directory / 'stream.m3u8'),
                        '-f', 'null', '-'], check=True, capture_output=True, timeout=30,
                       **process_options())
    finally:
        job.close()


@pytest.mark.integration
@pytest.mark.parametrize('encoder_mode', ['cpu', 'auto', 'fallback'])
def test_actual_reserve_rest_resume_and_close(tools, tmp_path, encoder_mode, monkeypatch):
    if encoder_mode == 'auto' and os.environ.get('LOCALCAST_TEST_GPU') != '1':
        pytest.skip('Hardware validation explicitly enabled only on a GPU test machine')
    ffmpeg, ffprobe = tools
    source = tmp_path / 'source.mkv'
    make_source(ffmpeg, source, seconds=120)
    clock = {'position': 0.0, 'state': 'PAUSED'}
    if encoder_mode == 'fallback':
        monkeypatch.setattr('localcast.transcoder.encoder_plans', lambda *args: [
            EncoderPlan('localcast_missing_encoder', 'GPU unavailable'), CPU,
        ])
    job = HlsJob(probe(source, ffprobe), tmp_path / 'cache', ffmpeg=ffmpeg,
                 encoder_mode='auto' if encoder_mode == 'fallback' else encoder_mode,
                 ahead_seconds=30, playback=lambda: dict(clock))
    process_id = job.process.pid
    try:
        job.wait_ready()
        until(lambda: job.snapshot()['resting'])
        state = job.snapshot()
        assert 30 <= state['buffer_ahead_seconds'] < 50, state
        assert state['encoded_seconds'] < 60, 'Must not convert the whole 120 second input'
        if encoder_mode == 'auto':
            assert state['hardware'] and 'NVIDIA' in state['encoder'], state
            assert job.plan.cuda_scale, state
        if encoder_mode == 'fallback':
            assert not state['hardware'] and state['fallbacks'], state
        owner = psutil.Process(job.process.pid)
        first = owner.cpu_times()
        encoded = state['encoded_seconds']
        time.sleep(0.5)
        second = owner.cpu_times()
        assert (second.user + second.system) - (first.user + first.system) < 0.1
        assert abs(job.snapshot()['encoded_seconds'] - encoded) < 1
        clock.update(position=state['published_seconds'] - 10, state='PLAYING')
        until(lambda: job.snapshot()['encoded_seconds'] > encoded + 4)
        until(lambda: job.snapshot()['resting'])
        # A lost receiver clock resumes work instead of leaving a frozen process.
        clock.update(position=None, state='UNKNOWN')
        until(lambda: not job.snapshot()['resting'])
        clock.update(position=0.0, state='PAUSED')
        until(lambda: job.snapshot()['resting'])
    finally:
        job.close()
    assert job.process.poll() is not None and not psutil.pid_exists(process_id)
    assert not job.directory.exists()
