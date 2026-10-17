"""Non-modal settings; destructive actions require a specific confirmation."""

import json
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class SettingsPanel(QDialog):
    cleanup_requested = Signal(str)
    import_requested = Signal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle('LocalCast • Configurações')
        self.setMinimumWidth(510)
        self.setModal(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)
        heading = QLabel('Configurações')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        row = QHBoxLayout()
        self.movies_button = QPushButton('Informações dos filmes / OMDb')
        self.movies_button.clicked.connect(parent.configure_movies)
        row.addWidget(self.movies_button)
        self.import_button = QPushButton('Importar configuração anterior')
        self.import_button.clicked.connect(self.import_settings)
        row.addWidget(self.import_button)
        layout.addLayout(row)
        heading = QLabel('Armazenamento e privacidade')
        heading.setObjectName('sectionTitle')
        layout.addWidget(heading)
        self.location = QLabel()
        self.location.setWordWrap(True)
        self.location.setObjectName('muted')
        layout.addWidget(self.location)
        self.summary = QLabel('Calculando espaço utilizado…')
        self.summary.setWordWrap(True)
        self.summary.setMinimumHeight(self.summary.fontMetrics().lineSpacing() * 3 + 8)
        layout.addWidget(self.summary)
        self.buttons = {}
        for operation, title in (
            ('history', 'Limpar histórico de reprodução'), ('logs', 'Limpar logs antigos'),
            ('cache', 'Limpar cache inativo'), ('reset', 'Restaurar padrões de fábrica'),
        ):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, op=operation: self.confirm(op))
            button.setAccessibleName(title)
            self.buttons[operation] = button
            layout.addWidget(button)
        self.buttons['reset'].setObjectName('danger')
        self.result = QLabel()
        self.result.setWordWrap(True)
        self.result.setObjectName('muted')
        layout.addWidget(self.result)
        close = QPushButton('Fechar')
        close.clicked.connect(self.close)
        layout.addWidget(close)

    def refresh_state(self, busy, connected):
        for name, button in self.buttons.items():
            button.setEnabled(not busy and not (connected and name in {'history', 'reset'}))
        self.import_button.setEnabled(not busy)
        self.movies_button.setEnabled(not busy)
        if connected:
            self.buttons['history'].setToolTip('Desconecte do Chromecast para limpar o histórico.')
            self.buttons['reset'].setToolTip('Desconecte do Chromecast para restaurar os padrões.')

    def show_sizes(self, sizes):
        self.location.setText('Dados locais: ' + sizes['path'])
        self.summary.setText(
            f"Histórico: {sizes['records']} vídeos · {sizes['history'] / 1024:.1f} KB\n"
            f"Logs: {sizes['logs'] / 1048576:.1f} MB\n"
            f"Conversões: {sizes['cache'] / 1048576:.1f} MB · "
            f"Capas e informações: {sizes['movie-cache'] / 1048576:.1f} MB"
        )
        self.adjustSize()

    def confirm(self, operation):
        descriptions = {
            'history': 'Apagar todas as posições salvas e o histórico dos vídeos?',
            'logs': 'Apagar os logs antigos? O log da sessão atual será preservado.',
            'cache': 'Apagar capas, informações em cache e conversões inativas? '
                     'Arquivos em uso serão preservados.',
            'reset': 'Apagar o histórico, a chave OMDb, as preferências, logs e caches inativos? '
                     'O aplicativo voltará às configurações iniciais.',
        }
        answer = QMessageBox.question(
            self, self.buttons[operation].text(), descriptions[operation] +
            '\n\nOs vídeos originais e o programa serão preservados. '
            'Esta operação não pode ser desfeita.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.cleanup_requested.emit(operation)

    def import_settings(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, 'Escolha movie-settings.json da versão anterior', '',
            'Configuração de filmes (movie-settings.json)',
        )
        if filename:
            self.import_requested.emit(filename)


def import_movie_settings(store, filename):
    path = Path(filename)
    if path.stat().st_size > 16384:
        raise ValueError('Arquivo de configuração maior que o esperado.')
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('key', ''), str):
        raise ValueError('Configuração de filmes inválida.')
    store.save_settings(raw.get('key', ''), bool(raw.get('automatic', True)))
