"""Offscreen Qt smoke test: no discovery or TV calls."""

import os
import time

from localcast.cast_client import Device
from localcast.movie_info import MovieDetails, MovieResult

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from localcast.gui import MainWindow


def test_gui_startup_tracks_and_async_shutdown(monkeypatch, tmp_path, track_info):
    monkeypatch.setenv("LOCALCAST_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("localcast.gui.environment_report", lambda: {"test": "no TV"})
    app = QApplication.instance() or QApplication([])
    window = MainWindow(port=0)
    window.show()
    deadline = time.monotonic() + 5
    while window._busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert not window._busy
    assert "Abrir MP4 / MKV" == window.open_button.text()
    assert not window.cast_button.isEnabled()
    assert not window.connect_button.isEnabled() and not window.windowIcon().isNull()
    window._done("discover", [Device("fake", "TV de teste", "192.168.1.50", "cast")])
    assert window.connect_button.isEnabled() and not window.cast_button.isEnabled()
    assert window.debug_panel.isHidden() and not window.debug_toggle.isChecked()
    messages = window.notes.toPlainText()
    window.debug_toggle.click()
    app.processEvents()
    assert window.debug_panel.isVisible() and window.notes.toPlainText() == messages
    window.debug_toggle.click()
    assert window.debug_panel.isHidden()
    window.network_toggle.click()
    assert window.network_fields.isVisible()
    window.known_host.setText("192.168.1.50")
    window.network_toggle.click()
    assert window.known_host.text() == "192.168.1.50" and window.network_fields.isHidden()
    window._done("analyze", track_info)
    assert "chave gratuita" in window.movie_panel.status.text()
    original_title = window.movie_panel.title.text()
    result = MovieResult(MovieDetails("Metadata only", actors="Actor A", imdb_rating="8.0"))
    window._movie_finished(window._movie_generation - 1, result)
    assert window.movie_panel.title.text() == original_title
    window._movie_finished(window._movie_generation, result)
    assert (
        window.movie_panel.actors.text() == "Actor A"
        and window.movie_panel.rotten_rating.text() == "—"
    )
    assert window.info is track_info and not window._busy
    assert window.audio_box.currentData() == 1
    assert window.subtitle_box.currentData() is None
    assert "Português" in window.audio_box.itemText(0)
    assert not window.subtitle_box.model().item(3).isEnabled()
    assert not window.apply_tracks_button.isEnabled()
    window.session.info = track_info
    window.session.mode = "hls"
    window._set_busy(False)
    assert not window.connect_button.isEnabled()
    window.audio_box.setCurrentIndex(window.audio_box.findData(4))
    assert window.apply_tracks_button.isEnabled()
    window.force_hls.setChecked(True)
    window.resolution.setCurrentIndex(window.resolution.findData(0))
    assert not window.audio_box.isEnabled() and not window.subtitle_box.isEnabled()
    assert not window.force_hls.isEnabled() and not window.apply_tracks_button.isEnabled()
    assert "Arquivo intacto" in window.conversion_hint.text()
    window.resolution.setCurrentIndex(window.resolution.findData(720))
    assert window.audio_box.isEnabled() and window.apply_tracks_button.isEnabled()
    assert window.force_hls.isEnabled() and window.force_hls.isChecked()
    window.session.mode = "original"
    window._set_busy(False)
    assert not window.apply_tracks_button.isEnabled()
    assert "transmita novamente" in window.tracks_hint.text()
    window.session.mode = None
    window.session.client.cast = object()  # Enable control only; no network operation.
    window._set_busy(False)
    assert window.disconnect_button.isEnabled()
    window.session.client.cast = None
    window.close()
    deadline = time.monotonic() + 5
    while not window._can_close and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    window.worker.thread.join(timeout=1)
    window.movie_worker.thread.join(timeout=1)
    assert window._can_close and not window.worker.thread.is_alive()
    assert not window.movie_worker.thread.is_alive()
