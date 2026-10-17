import time
from dataclasses import replace
from unittest.mock import Mock

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication, QMessageBox

from localcast.cast_client import Device
from localcast.gui import MainWindow
from localcast.history import VideoIdentity


def settle(app, window):
    deadline = time.monotonic() + 5
    while window._busy and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    assert not window._busy


def test_resume_controls_confirmation_and_factory_defaults(tmp_path, monkeypatch, media_info):
    monkeypatch.setenv('LOCALCAST_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('localcast.gui.environment_report', lambda: {})
    app = QApplication.instance() or QApplication([])
    window = MainWindow(port=0)
    try:
        window.show()
        settle(app, window)
        identity = VideoIdentity.from_path(media_info.path)
        window.history.save(identity, 45, 120, 0)
        window._done('analyze', (media_info, window.history.get(identity)))
        window._done('discover', [Device('mock', 'TV simulada', '192.168.1.5', 'cast')])
        assert window.cast_button.text() == 'Continuar'
        assert '00:00:45' in window.resume_label.text()
        assert window.resume_bar.value() == 375 and window.restart_button.isVisible()
        window.configure_settings()
        settle(app, window)
        panel = window.settings_panel
        monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Cancel)
        panel.confirm('history')
        assert window.history.count() == 1 and not window._busy
        monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
        panel.confirm('history')
        settle(app, window)
        assert window.history.count() == 0
        assert window.cast_button.text() == 'Reproduzir' and window.restart_button.isHidden()
        window.resolution.setCurrentIndex(1)
        window.encoder_box.setCurrentIndex(1)
        window.ahead_seconds.setValue(240)
        window.movie_store.save_settings('TEST_KEY', False)
        panel.confirm('reset')
        settle(app, window)
        assert window.info is None and window.ahead_seconds.value() == 90
        assert window.encoder_box.currentData() == 'auto'
        assert not window.movie_store.settings()['key']
        assert not window.cast_button.isEnabled()
        assert media_info.path.exists()
    finally:
        window.close()
        deadline = time.monotonic() + 5
        while not window._can_close and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window._can_close
        from localcast.diagnostics import close_logging
        close_logging()


def test_drop_accepts_only_one_local_video(tmp_path, monkeypatch, media_info):
    from types import SimpleNamespace
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(media_info.path))])
    event = SimpleNamespace(mimeData=lambda: mime)
    assert MainWindow._drop_path(None, event) == media_info.path
    mime.setUrls([QUrl('https://example.com/movie.mkv')])
    assert MainWindow._drop_path(None, event) is None
    mime.setUrls([QUrl.fromLocalFile(str(media_info.path))] * 2)
    assert MainWindow._drop_path(None, event) is None


def test_saved_progress_refreshes_and_continue_cannot_reload_active_film(tmp_path, monkeypatch, media_info):
    monkeypatch.setenv('LOCALCAST_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('localcast.gui.environment_report', lambda: {})
    app = QApplication.instance() or QApplication([])
    window = MainWindow(0)
    try:
        window.show()
        settle(app, window)
        window.timer.stop()
        device = Device('mock', 'TV simulada', '192.168.1.5', 'cast')
        identity = VideoIdentity.from_path(media_info.path)
        window.history.save(identity, 45, 120, window.history.epoch)
        window._done('analyze', (media_info, window.history.get(identity)))
        window._done('discover', [device])
        window.device_box.setCurrentIndex(0)
        deadline = time.monotonic() + 5
        while window._history_refresh_pending and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        window.session.client = Mock(cast=None)
        status = {'connected': True, 'player_state': 'PLAYING', 'current_time': 90}
        window.session.client.reported_snapshot.return_value = status
        window.session.client.snapshot.return_value = status
        window.session.info = window.session.source_info = media_info
        window.session.device = device
        window.session.mode = 'direct'
        window.history.save(identity, 85, 120, window.history.epoch)
        window._history_refresh_at = 0
        window.refresh()
        assert not window._busy  # No freeze/disabled controls while SQLite is read.
        deadline = time.monotonic() + 5
        while window._history_refresh_pending and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window.history_row['position'] == 85
        assert '00:01:25' in window.resume_label.text()
        assert window.resume_bar.value() == round(85 / 120 * 1000)
        assert window.cast_button.text() == 'Em reprodução'
        assert not window.cast_button.isEnabled()
        start = Mock()
        monkeypatch.setattr(window.session, 'start', start)
        window.cast_file()
        start.assert_not_called()
        status['player_state'] = 'PAUSED'
        window.refresh()
        window.cast_file()
        start.assert_not_called()

        # Ignore responses for an old selection or a history cleared while reading.
        other = replace(media_info, path=tmp_path / 'other.mp4')
        window.info = other
        window._done('history-refresh', (media_info, window.history.epoch, {'position': 1}))
        assert window.history_row['position'] == 85
        window.info = media_info
        epoch = window.history.epoch
        window.history.clear()
        window.history_row = None
        window._done('history-refresh', (media_info, epoch, {'position': 1}))
        assert window.history_row is None

        # A stale label must never decide where a NEW playback session starts.
        window.session.mode = None
        window.history.save(identity, 45, 120, window.history.epoch)
        window.history_row = window.history.get(identity)
        window.history.save(identity, 95, 120, window.history.epoch)
        monkeypatch.setattr(window, 'task', lambda name, operation: operation())
        window.cast_file()
        assert start.call_args.kwargs['start_position'] == 95
        window.cast_file(restart=True)
        assert start.call_args.kwargs['start_position'] == 0
        window._failed('history-refresh', 'temporary read failure')
        assert not window._history_refresh_pending and not window._busy

        window.history.save(identity, 115, 120, window.history.epoch)
        window._done('history-refresh', (media_info, window.history.epoch, window.history.get(identity)))
        assert window.cast_button.text() == 'Assistir novamente'
        assert 'Concluído' in window.resume_label.text() and window.resume_bar.isVisible()
    finally:
        window.session.mode = None
        window.close()
        deadline = time.monotonic() + 5
        while not window._can_close and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window._can_close
