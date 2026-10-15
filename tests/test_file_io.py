import os
import threading
import time

from localcast.file_io import open_shared_binary, read_shared_text
from localcast.transcoder import HlsJob


def test_playlist_snapshot_and_replace_after_close(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    temporary = tmp_path / "stream.m3u8.tmp"
    playlist.write_bytes(b"#EXTM3U\nold.ts\n")
    temporary.write_bytes(b"#EXTM3U\nnew.ts\n#EXT-X-ENDLIST\n")
    with open_shared_binary(playlist) as snapshot:
        assert snapshot.read() == b"#EXTM3U\nold.ts\n"
    os.replace(temporary, playlist)
    assert read_shared_text(playlist) == "#EXTM3U\nnew.ts\n#EXT-X-ENDLIST\n"


def test_recovers_completed_ffmpeg_playlist_after_windows_lock(tmp_path):
    playlist = tmp_path / "stream.m3u8"
    temporary = tmp_path / "stream.m3u8.tmp"
    playlist.write_bytes(b"#EXTM3U\nold.ts\n")
    temporary.write_bytes(b"#EXTM3U\nnew.ts\n#EXT-X-ENDLIST\n")
    job = HlsJob.__new__(HlsJob)
    job.directory = tmp_path
    job._stop = threading.Event()
    job.error = None
    with open_shared_binary(playlist):
        publisher = threading.Thread(target=job._publish_pending_playlist)
        publisher.start()
        time.sleep(0.08)
    publisher.join(timeout=4)
    assert not publisher.is_alive() and job.error is None
    assert "#EXT-X-ENDLIST" in read_shared_text(playlist)
