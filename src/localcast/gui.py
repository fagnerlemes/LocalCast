"""Qt interface with a serial command worker; all slow IO runs off the main thread."""

import json
import logging
import queue
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
)

from . import __version__
from .diagnostics import environment_report, hints, write_report
from .movie_info import MovieClient, MovieStore, MovieWorker, guess_movie
from .movie_panel import MovieCorrection, MovieSettings
from .session import PlaybackSession
from .ui_assets import asset_path
from .ui_layout import build_ui
from .ui_theme import apply_theme, window_chrome

LOG = logging.getLogger(__name__)
COMMAND_NAMES = {
    "environment": "Conferindo ferramentas",
    "discover": "Buscando Chromecast",
    "standby": "Conectando e mostrando tela de espera",
    "analyze": "Analisando arquivo",
    "start": "Transmitindo",
    "tracks": "Aplicando áudio e legenda",
    "disconnect": "Desconectando Chromecast",
    "stop": "Parando vídeo",
    "play": "Retomando vídeo",
    "pause": "Pausando vídeo",
    "seek": "Mudando a posição",
    "report": "Salvando diagnóstico",
}


class CommandWorker(QObject):
    done = Signal(str, object)
    failed = Signal(str, str)
    closed = Signal()

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.commands = queue.Queue()
        self.thread = threading.Thread(target=self.run, name="localcast-commands", daemon=False)
        self.thread.start()

    def submit(self, name, func):
        self.commands.put((name, func))

    def run(self):
        while True:
            name, func = self.commands.get()
            try:
                result = func()
                self.done.emit(name, result)
            except Exception as exc:
                LOG.exception("Comando %s falhou", name)
                self.failed.emit(name, str(exc))
            if name == "close":
                self.closed.emit()
                return


def clock_text(seconds: float) -> str:
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


class MainWindow(QMainWindow):
    def __init__(self, port=8765):
        super().__init__()
        apply_theme()
        icon = QIcon(str(asset_path("localcast.ico")))
        if icon.isNull():
            icon = QIcon(str(asset_path("localcast-logo.png")))
        self.setWindowIcon(icon)
        QApplication.instance().setWindowIcon(icon)
        self.setWindowTitle(f"LocalCast {__version__} • MP4 / MKV • Chromecast")
        self.setMinimumSize(920, 620)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(
            min(1120, available.width() - 70) if available else 1120,
            min(860, available.height() - 70) if available else 860,
        )
        self.session = PlaybackSession(port)
        self.worker = CommandWorker(self.session)
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.closed.connect(self._closed)
        self.info = None
        self.devices = []
        self._busy = False
        self._closing = False
        self._can_close = False
        self._last_state = None
        self._last_hint = None
        self.movie_store = MovieStore()
        self.movie_worker = MovieWorker(MovieClient(self.movie_store))
        self.movie_worker.finished.connect(self._movie_finished)
        self.movie_worker.failed.connect(self._movie_failed)
        self.movie_query = None
        self._movie_generation = 0

        build_ui(self)
        self._editable = (
            self.search,
            self.connect_button,
            self.device_box,
            self.open_button,
            self.cast_button,
            self.play_button,
            self.pause_button,
            self.stop_button,
            self.seek_button,
            self.slider,
            self.seek_seconds,
            self.known_host,
            self.lan_ip,
            self.force_hls,
            self.resolution,
            self.report_button,
            self.audio_box,
            self.subtitle_box,
            self.apply_tracks_button,
            self.disconnect_button,
        )
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(750)
        self._set_busy(False)
        self.task("environment", environment_report)

    def note(self, message):
        self.notes.appendPlainText(message)

    def _set_busy(self, busy):
        self._busy = busy
        for widget in self._editable:
            widget.setEnabled(not busy and not self._closing)
        if not busy and not self._closing:
            active = self.session.mode is not None
            self.cast_button.setEnabled(self.info is not None and bool(self.devices))
            self.connect_button.setEnabled(bool(self.devices) and not active)
            for widget in (self.play_button, self.pause_button, self.stop_button):
                widget.setEnabled(active)
            for widget in (self.slider, self.seek_button, self.seek_seconds):
                widget.setEnabled(active and self.session.info.duration > 0)
            self.disconnect_button.setEnabled(bool(self.session.client.cast))
        self._conversion_changed()

    def _conversion_changed(self):
        original = self.resolution.currentData() == 0
        editable = not self._busy and not self._closing
        self.force_hls.setEnabled(editable and not original)
        self.audio_box.setEnabled(
            editable and not original and bool(self.info and self.info.audio_tracks)
        )
        self.subtitle_box.setEnabled(
            editable and not original and bool(self.info and self.info.subtitle_tracks)
        )
        self.conversion_hint.setText(
            "Arquivo intacto; a compatibilidade depende do Chromecast. Clique Transmitir para aplicar."
            if original
            else "MP4 compatível vai direto. Outros arquivos usam H.264/AAC."
        )
        self._tracks_changed()

    def _populate_tracks(self):
        self.audio_box.blockSignals(True)
        self.subtitle_box.blockSignals(True)
        self.audio_box.clear()
        for ordinal, track in enumerate(self.info.audio_tracks, 1):
            self.audio_box.addItem(f"{ordinal}. {track.label}", track.index)
        self.audio_box.addItem("Sem áudio", -1)
        default_item = self.audio_box.findData(self.info.audio_index)
        self.audio_box.setCurrentIndex(
            default_item if default_item >= 0 else self.audio_box.count() - 1
        )
        self.subtitle_box.clear()
        self.subtitle_box.addItem(
            "Sem legenda" if self.info.subtitle_tracks else "Sem legenda no arquivo", None
        )
        for ordinal, track in enumerate(self.info.subtitle_tracks, 1):
            self.subtitle_box.addItem(f"{ordinal}. {track.label}", track.index)
            if track.kind == "unsupported":
                self.subtitle_box.model().item(self.subtitle_box.count() - 1).setEnabled(False)
        self.audio_box.blockSignals(False)
        self.subtitle_box.blockSignals(False)
        self._tracks_changed()

    def _tracks_changed(self):
        if not hasattr(self, "apply_tracks_button"):
            return
        same_file = bool(
            self.info and self.session.info and self.info.path == self.session.info.path
        )
        audio_index = self.audio_box.currentData()
        selected_audio = None if audio_index == -1 else audio_index
        subtitle_index = self.subtitle_box.currentData()
        current_subtitle = self.session.subtitle.index if self.session.subtitle else None
        pending = bool(
            same_file
            and (
                selected_audio != self.session.info.audio_index
                or subtitle_index != current_subtitle
            )
        )
        self.apply_tracks_button.setEnabled(
            not self._busy
            and not self._closing
            and bool(self.session.mode)
            and pending
            and self.resolution.currentData() != 0
            and self.session.mode != "original"
        )
        self.tracks_hint.setText(
            "Original: áudio e legendas são definidos pelo Chromecast."
            if self.resolution.currentData() == 0
            else "Para selecionar as faixas, transmita novamente com conversão automática."
            if self.session.mode == "original"
            else "Legenda incorporada ao vídeo. Use Aplicar faixas para trocar."
            if subtitle_index is not None
            else "Escolha áudio e legenda. Durante o vídeo, use Aplicar faixas para trocar."
        )

    def apply_tracks(self):
        audio, subtitle = self.audio_box.currentData(), self.subtitle_box.currentData()
        self.task("tracks", lambda: self.session.set_tracks(audio, subtitle))

    def task(self, name, func):
        if self._busy or self._closing:
            return
        self._set_busy(True)
        self.state_label.setText(f"{COMMAND_NAMES.get(name, name)}…")
        self.worker.submit(name, func)

    def discover(self):
        host = self.known_host.text().strip() or None
        self.task("discover", lambda: self.session.discover(host))

    def open_file(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Abrir vídeo", "", "Vídeos (*.mp4 *.mkv);;Todos os arquivos (*)"
        )
        if filename:
            self.task("analyze", lambda: self.session.analyze(Path(filename)))

    def connect_standby(self):
        device = self.device_box.currentData()
        if device:
            ip = self.lan_ip.text().strip() or None
            self.task("standby", lambda: self.session.show_standby(device, ip))

    def cast_file(self):
        device = self.device_box.currentData()
        if not device or not self.info:
            return
        info = self.info
        original = self.resolution.currentData() == 0
        force, height = (
            not original and self.force_hls.isChecked(),
            self.resolution.currentData() or 1080,
        )
        ip = self.lan_ip.text().strip() or None
        audio, subtitle = self.audio_box.currentData(), self.subtitle_box.currentData()
        if original:
            audio, subtitle = None, None
        self.note(
            "Enviando o arquivo original, sem conversão. A reprodução depende do suporte do Chromecast."
            if original
            else "Preparando HLS e aguardando receiver (pode levar até 90 s + 30 s)."
            if force or not info.direct_ok or subtitle is not None or audio == -1
            else "Enviando MP4 direto ao Default Media Receiver."
        )
        self.task(
            "start",
            lambda: self.session.start(
                info,
                device,
                force,
                height,
                ip,
                audio_index=audio,
                subtitle_index=subtitle,
                original=original,
            ),
        )

    def action(self, action):
        self.task(action, lambda: self.session.command(action))

    def seek(self, seconds):
        self.task("seek", lambda: self.session.seek(seconds))

    @Slot(str, object)
    def _done(self, name, result):
        if self._closing:
            return
        if name == "discover":
            self.devices = result
            self.device_box.clear()
            for device in result:
                self.device_box.addItem(f"{device.name} • {device.host} • {device.model}", device)
            self.note(
                "Arquivo original será enviado sem conversão, conforme a opção escolhida."
                if self.resolution.currentData() == 0
                else f"{len(result)} Chromecast(s)."
                if result
                else "Nenhum Chromecast. Confira rede privada, mDNS UDP 5353, VPN e isolamento de clientes; tente o IP do aparelho."
            )
        elif name == "analyze":
            self.info = result
            self.file_label.setText(result.path.name)
            self.media_label.setText(result.summary())
            self._populate_tracks()
            self.movie_query = guess_movie(result.path)
            self.movie_panel.reset(self.movie_query)
            self.request_movie()
            self.note(
                "MP4 elegível para reprodução direta."
                if result.direct_ok
                else "Conversão HLS: " + "; ".join(result.direct_reasons)
            )
        elif name == "environment":
            self.note(json.dumps(result, ensure_ascii=False, indent=2))
        elif name == "report":
            self.note("Diagnóstico salvo.")
        elif name == "disconnect":
            self.devices = []
            self.device_box.clear()
            self.note("Chromecast desconectado. Busque novamente para transmitir.")
        elif name == "standby":
            self.note("Tela de espera enviada. Abra um MP4/MKV e clique Transmitir para começar.")
        else:
            self.note(f"{COMMAND_NAMES.get(name, name)}: concluído.")
        self._set_busy(False)
        self.refresh()

    @Slot(str, str)
    def _failed(self, name, message):
        if self._closing:
            return
        self.note(f"ERRO [{name}]: {message}")
        if name == "disconnect":
            self.devices = []
            self.device_box.clear()
        self._set_busy(False)
        self.state_label.setText(f"Falha em {name}. Consulte o diagnóstico e o log.")
        QMessageBox.warning(self, "LocalCast • erro", message)

    def refresh(self):
        state = self.session.snapshot()
        if self._busy or self._closing:
            return
        duration = state.get("total_duration") or 0
        position = min(state.get("position", 0), duration) if duration else 0
        self.time_label.setText(f"{clock_text(position)} / {clock_text(duration)}")
        self.slider.setMaximum(max(0, int(duration) - 1))
        self.seek_seconds.setMaximum(max(0, int(duration) - 1))
        if not self.slider.isSliderDown():
            self.slider.setValue(int(position))
        mode = {
            "original": "original, sem conversão",
            "direct": "MP4 direto",
            "hls": "conversão HLS",
        }.get(state.get("mode"), "tela de espera" if state.get("standby_active") else "sem sessão")
        player = (
            "pronto para transmitir"
            if state.get("standby_active")
            else state.get("player_state") or "aguardando"
        )
        summary = (
            f"{mode} | {player} | IP PC: {state.get('lan_ip') or 'automático'}:{state.get('port')}"
        )
        if state.get("transcode"):
            tc = state["transcode"]
            summary += f" | FFmpeg {tc['speed']:.2f}×, {tc['encoded_seconds']:.0f}s produzidos"
        self.state_label.setText(summary)
        self._tracks_changed()
        diagnostic = "\n".join(hints(state))
        if diagnostic and diagnostic != self._last_hint:
            self.note(diagnostic)
        self._last_hint = diagnostic
        player_state = (
            state.get("player_state"),
            state.get("idle_reason"),
            state.get("load_error"),
        )
        if player_state != self._last_state and state.get("mode"):
            self.note(f"Receiver: {player_state}")
        self._last_state = player_state

    def save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar diagnóstico", "localcast-diagnostico.json", "JSON (*.json)"
        )
        if path:
            snapshot = self.session.snapshot()
            self.task("report", lambda: write_report(Path(path), snapshot))

    def configure_movies(self):
        dialog = MovieSettings(self.movie_store, self)
        if dialog.exec() == dialog.DialogCode.Accepted and self.info:
            self.request_movie(refresh=True)

    def correct_movie(self):
        if not self.movie_query:
            return
        dialog = MovieCorrection(self.movie_query, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            try:
                self.movie_query = dialog.query()
            except ValueError as exc:
                QMessageBox.warning(self, "Identificar filme", str(exc))
                return
            self.movie_panel.reset(self.movie_query)
            self.request_movie(refresh=True, manual=True)

    def refresh_movie(self):
        self.request_movie(refresh=True, manual=True)

    def request_movie(self, refresh=False, manual=False):
        if not self.movie_query or self._closing:
            return
        self._movie_generation += 1
        settings = self.movie_store.settings()
        self.movie_panel.set_buttons(True)
        if not settings["key"]:
            self.movie_panel.status.setText(
                "Configure uma chave gratuita em Configurar filmes para buscar capa, notas e elenco."
            )
            return
        if not manual and not settings["automatic"]:
            self.movie_panel.status.setText(
                "Consulta automática desativada. Use Atualizar para buscar este filme."
            )
            return
        self.movie_panel.status.setText(
            "Buscando capa, notas e elenco… A reprodução continua disponível."
        )
        self.movie_panel.set_buttons(True, loading=True)
        self.movie_worker.submit(self._movie_generation, self.movie_query, settings["key"], refresh)

    @Slot(int, object)
    def _movie_finished(self, generation, result):
        if self._closing or generation != self._movie_generation:
            return
        self.movie_panel.show_result(result)

    @Slot(int, str)
    def _movie_failed(self, generation, message):
        if self._closing or generation != self._movie_generation:
            return
        self.movie_panel.status.setText(message)
        self.movie_panel.set_buttons(True)
        self.note("Informações do filme: " + message)

    def showEvent(self, event):
        super().showEvent(event)
        window_chrome(self)

    def closeEvent(self, event: QCloseEvent):
        if self._can_close:
            event.accept()
            return
        event.ignore()
        if not self._closing:
            self._closing = True
            self.movie_worker.close()
            self.timer.stop()
            self._set_busy(True)
            self.state_label.setText("Desconectando Chromecast e encerrando operações…")
            self.worker.submit("close", self.session.close)

    @Slot()
    def _closed(self):
        self._can_close = True
        self.close()


def launch(port=8765, smoke_report=None):
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("LocalCast")
    app.setApplicationVersion(__version__)
    window = MainWindow(port)
    window.show()
    if smoke_report:

        def check_packaged_gui():
            from PySide6.QtWidgets import QLabel

            mark = window.findChild(QLabel, "brandLogo")
            report = environment_report()
            report["window_icon"] = not window.windowIcon().isNull()
            report["header_logo"] = bool(mark and not mark.pixmap().isNull())
            report["standby_asset"] = asset_path("localcast-espera.mp4").is_file()
            report["hidden_debug"] = window.debug_panel.isHidden()
            smoke_report.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(smoke_report.with_suffix(".png")))
            smoke_report.write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            window.close()

        QTimer.singleShot(1500, check_packaged_gui)
    return app.exec()
