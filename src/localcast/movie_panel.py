"""Movie card, poster and optional source settings. All text from the service is plain text."""

from datetime import datetime
from urllib.parse import quote

from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .movie_info import MovieQuery, MovieResult


def label(text="", name="", wrap=False):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


class Poster(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(142, 213)
        self.image = QPixmap()
        self.setAccessibleName("Capa do filme")

    def set_image(self, data):
        self.image = QPixmap()
        if data:
            self.image.loadFromData(data)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), QColor("#2b2e35"))
        if not self.image.isNull():
            image = self.image.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - image.width()) // 2, (self.height() - image.height()) // 2, image
            )
        else:
            painter.setPen(QColor("#b3b8c2"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "LocalCast\n\nCapa do filme"
            )


class MoviePanel(QFrame):
    configure_requested = Signal()
    correct_requested = Signal()
    refresh_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("moviePanel")
        self.result = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(label("Sobre o filme", "sectionTitle"))
        row.addStretch()
        row.addWidget(label("OMDb", "badge"))
        layout.addLayout(row)
        self.title = label("Seu próximo filme", "movieTitle", True)
        self.meta = label("Abra um MP4 ou MKV para começar.", "muted", True)
        row = QHBoxLayout()
        row.setSpacing(20)
        self.poster = Poster()
        row.addWidget(self.poster, 0, Qt.AlignmentFlag.AlignTop)
        ratings = QVBoxLayout()
        ratings.setSpacing(5)
        ratings.addWidget(self.title)
        ratings.addWidget(self.meta)
        ratings.addSpacing(8)
        ratings.addWidget(label("Nota IMDb", "muted"))
        self.imdb_rating = label("—", "rating")
        ratings.addWidget(self.imdb_rating)
        self.votes = label("Sem consulta", "muted", True)
        ratings.addWidget(self.votes)
        ratings.addSpacing(8)
        ratings.addWidget(label("Rotten Tomatoes®", "muted", True))
        self.rotten_rating = label("—", "rating")
        ratings.addWidget(self.rotten_rating)
        self.rotten_hint = label("Quando disponível", "muted", True)
        ratings.addWidget(self.rotten_hint)
        ratings.addStretch()
        row.addLayout(ratings, 1)
        layout.addLayout(row)
        self.plot = label(
            "Capa, notas e elenco ficam aqui. A consulta não interfere na reprodução.", "", True
        )
        layout.addWidget(self.plot)
        layout.addWidget(label("Elenco principal", "sectionTitle"))
        self.actors = label("Ainda não consultado", "muted", True)
        layout.addWidget(self.actors)
        self.director = label("", "muted", True)
        layout.addWidget(self.director)
        layout.addStretch()
        self.status = label(
            "Configure a fonte gratuita para identificar o filme pelo nome do arquivo.",
            "muted",
            True,
        )
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.correct = QPushButton("Corrigir identificação")
        self.refresh = QPushButton("Atualizar")
        self.correct.clicked.connect(self.correct_requested.emit)
        self.refresh.clicked.connect(self.refresh_requested.emit)
        row.addWidget(self.correct)
        row.addWidget(self.refresh)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.imdb_link = QPushButton("Ver no IMDb")
        self.rotten_link = QPushButton("Consultar Rotten Tomatoes")
        for button in (self.imdb_link, self.rotten_link):
            button.setObjectName("link")
            row.addWidget(button)
        self.imdb_link.clicked.connect(lambda: self.open_source("imdb"))
        self.rotten_link.clicked.connect(lambda: self.open_source("rotten"))
        layout.addLayout(row)
        self.set_buttons(False)

    def set_buttons(self, has_file, loading=False):
        self.correct.setEnabled(has_file)
        self.refresh.setEnabled(has_file and not loading)
        self.imdb_link.setEnabled(bool(self.result and self.result.details.imdb_id))
        self.rotten_link.setEnabled(bool(self.result))

    def reset(self, query: MovieQuery):
        self.result = None
        self.title.setText(query.title)
        self.meta.setText(query.year or "Identificação pelo nome do arquivo")
        self.poster.set_image(b"")
        self.imdb_rating.setText("—")
        self.rotten_rating.setText("—")
        self.votes.setText("Ainda não consultado")
        self.rotten_hint.setText("Quando disponível")
        self.plot.setText("A reprodução está disponível mesmo sem informações online.")
        self.actors.setText("Ainda não consultado")
        self.director.setText("")
        self.set_buttons(True)

    def show_result(self, result: MovieResult):
        self.result = result
        movie = result.details
        self.title.setText(movie.title)
        self.meta.setText(
            "  •  ".join(part for part in (movie.year, movie.runtime, movie.genre) if part)
        )
        self.poster.set_image(result.poster)
        self.imdb_rating.setText(movie.imdb_rating + " / 10" if movie.imdb_rating else "—")
        self.votes.setText(
            movie.imdb_votes + " votos" if movie.imdb_votes else "Nota não informada"
        )
        self.rotten_rating.setText(movie.rotten_rating or "—")
        self.rotten_hint.setText(
            "Crítica, via OMDb" if movie.rotten_rating else "Não informado pela fonte"
        )
        self.plot.setText(movie.plot or "Sinopse não informada pela fonte.")
        self.actors.setText(movie.actors or "Elenco não informado pela fonte.")
        self.director.setText("Direção: " + movie.director if movie.director else "")
        date = (
            datetime.fromtimestamp(movie.updated_at).strftime("%d/%m/%Y")
            if movie.updated_at
            else ""
        )
        self.status.setText(
            "Dados e imagem via OMDb · "
            + ("cache de " if result.cached else "consultado em ")
            + date
        )
        self.set_buttons(True)

    def open_source(self, source):
        if not self.result:
            return
        movie = self.result.details
        url = (
            "https://www.imdb.com/title/" + movie.imdb_id + "/"
            if source == "imdb"
            else movie.rotten_url
            or "https://www.rottentomatoes.com/search?search=" + quote(movie.title)
        )
        QDesktopServices.openUrl(QUrl(url))


class MovieSettings(QDialog):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("Configurar informações dos filmes")
        self.setMinimumWidth(510)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label("Informações dos filmes", "sectionTitle"))
        layout.addWidget(
            label(
                "OMDb fornece capa, elenco e notas. O plano gratuito atende ao uso pessoal; a nota Rotten Tomatoes pode não estar disponível. Sinopse e elenco podem vir em inglês.",
                "muted",
                True,
            )
        )
        settings = store.settings()
        self.key = QLineEdit(settings["key"])
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Cole a chave recebida por e-mail")
        self.key.setAccessibleName("Chave da API OMDb")
        form = QFormLayout()
        form.addRow("Chave OMDb", self.key)
        layout.addLayout(form)
        self.automatic = QCheckBox("Consultar automaticamente ao abrir um arquivo")
        self.automatic.setChecked(settings["automatic"])
        layout.addWidget(self.automatic)
        layout.addWidget(
            label(
                "A consulta envia apenas o título/ano ou ID IMDb; o vídeo não é enviado. A chave fica nesta pasta de dados e não entra no diagnóstico exportado.",
                "muted",
                True,
            )
        )
        link = QPushButton("Obter chave gratuita no OMDb")
        link.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl("https://www.omdbapi.com/apikey.aspx"))
        )
        layout.addWidget(link)
        layout.addWidget(
            label(
                "Dados: OMDb · licença CC BY-NC 4.0. LocalCast não é afiliado ao IMDb ou ao Rotten Tomatoes. Dados e notas podem estar incompletos ou desatualizados.",
                "muted",
                True,
            )
        )
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            self.store.save_settings(self.key.text(), self.automatic.isChecked())
            self.accept()
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Configurar filmes", str(exc))


class MovieCorrection(QDialog):
    def __init__(self, query: MovieQuery, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Corrigir identificação do filme")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(label("Qual é o filme?", "sectionTitle"))
        layout.addWidget(
            label(
                "Informe o título, ID IMDb (tt...) ou link da página IMDb. O nome do seu arquivo será preservado.",
                "muted",
                True,
            )
        )
        form = QFormLayout()
        self.title = QLineEdit(query.imdb_id or query.title)
        self.year = QLineEdit(query.year)
        self.year.setPlaceholderText("Opcional")
        form.addRow("Título ou IMDb", self.title)
        form.addRow("Ano", self.year)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Buscar filme")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def query(self):
        import re

        title = self.title.text().strip()
        imdb = re.search(r"\btt\d{5,12}\b", title, re.I)
        year = self.year.text().strip()
        if not title or (year and not re.fullmatch(r"(?:18|19|20)\d{2}", year)):
            raise ValueError("Informe um título e um ano válido, ou deixe o ano em branco.")
        return MovieQuery(title, year, imdb.group().lower() if imdb else "")
