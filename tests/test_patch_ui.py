import time
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QMimeData, QRect, QUrl
from PySide6.QtWidgets import QApplication

from localcast.gui import MainWindow
from localcast.movie_info import MovieDetails, MovieResult


def test_volume_drag_and_default_window(monkeypatch, tmp_path, track_info):
    track_info.path.write_bytes(b'drag test')
    monkeypatch.setenv('LOCALCAST_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.setattr('localcast.gui.environment_report', lambda: {})
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(QApplication, 'primaryScreen', lambda: SimpleNamespace(
        availableGeometry=lambda: QRect(0, 0, 1920, 1040)))
    window = MainWindow(0)
    try:
        window.show()
        deadline = time.monotonic() + 5
        while window._busy and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window.size().width() == 1120 and window.size().height() == 980
        assert window.drop_hint.text() == 'ou arraste e solte'
        window._done('analyze', track_info)
        app.processEvents()
        assert window.controls_scroll.verticalScrollBar().maximum() == 0
        with monkeypatch.context() as scoped:
            from localcast.cast_client import Device
            window.device_box.addItem('TV de teste', Device('u', 'TV', '192.168.1.50', 'cast'))
            window.device_box.setCurrentIndex(window.device_box.count() - 1)
            start = Mock()
            scoped.setattr(window.session, 'start', start)
            scoped.setattr(window, 'task', lambda name, operation: operation())
            window.movie_panel.show_result(MovieResult(MovieDetails('Filme identificado'), b'poster'))
            window.cast_file()
            assert start.call_args.kwargs['display_title'] == 'Filme identificado'
            assert start.call_args.kwargs['cover'] == b'poster'
            window._done('analyze', track_info)
            window.cast_file()
            assert start.call_args.kwargs['cover'] == b''  # Never reuse another file's cover.
            assert start.call_args.kwargs['display_title'] != 'Filme identificado'
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(track_info.path))])
        event = SimpleNamespace(mimeData=lambda: mime, acceptProposedAction=Mock(), ignore=Mock())
        window.dragEnterEvent(event)
        assert window.drop_overlay.isVisible() and window.file_card.property('dropActive')
        window.dragLeaveEvent(SimpleNamespace(accept=Mock()))
        assert window.drop_overlay.isHidden()
        window.dragEnterEvent(event)
        selected = Mock()
        monkeypatch.setattr(window, 'select_file', selected)
        window.dropEvent(event)
        selected.assert_called_once_with(track_info.path)
        assert window.drop_overlay.isHidden()
        mime.setUrls([QUrl('https://example.com/movie.mkv')])
        window.dragEnterEvent(event)
        assert window.drop_overlay.isHidden()

        cast = SimpleNamespace(status=SimpleNamespace(volume_level=.3, volume_muted=False),
                               socket_client=SimpleNamespace(is_connected=True), app_id='CC1AD845')
        window.session.client.cast = cast
        submit = Mock()
        monkeypatch.setattr(window.worker, 'submit', submit)
        state = {'connected': True, 'volume_level': .3, 'volume_muted': False}
        window._refresh_volume(state)
        assert window.volume_slider.value() == 30 and window.volume_value.text() == '30%'
        assert window._pending_volume is None  # Receiver updates never send commands.
        window.volume_slider.setValue(40)
        window.volume_slider.setValue(60)
        window._flush_volume()
        assert submit.call_count == 1 and window._volume_inflight
        window.volume_slider.setValue(70)
        window._flush_volume()
        assert submit.call_count == 1  # A drag never grows an unbounded queue.
        window._done('volume', 60)
        assert submit.call_count == 2
        window._pending_volume = (80, cast)
        window.session.client.cast = None
        window._done('volume', 70)
        assert submit.call_count == 2  # Never send an old request to a new device.
        window._refresh_volume({'connected': False})
        assert not window.volume_slider.isEnabled() and window.volume_value.text() == '—'
    finally:
        monkeypatch.undo()
        window.session.client.cast = None
        window.close()
        deadline = time.monotonic() + 5
        while not window._can_close and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert window._can_close
