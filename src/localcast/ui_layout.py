"""Interface composition. Keeps all existing widget names and playback callbacks."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import __author__
from .movie_panel import MoviePanel, label
from .ui_assets import asset_path
from .ui_theme import DarkComboBox, DarkSpinBox


def card(title):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(8)
    layout.addWidget(label(title, "sectionTitle"))
    return frame, layout


def scroller(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    return area


def build_ui(self):
    root = QWidget()
    root.setObjectName("root")
    self.setCentralWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(22, 18, 22, 16)
    layout.setSpacing(16)
    header = QHBoxLayout()
    header.setSpacing(12)
    mark = label("LC", "brandMark")
    mark.setFixedSize(46, 46)
    mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
    mark.setAccessibleName("Logo do LocalCast")
    logo = QPixmap(str(asset_path("localcast-logo.png")))
    if not logo.isNull():
        logo = logo.scaled(
            92, 92, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        logo.setDevicePixelRatio(2)
        mark.setObjectName("brandLogo")
        mark.setPixmap(logo)
    header.addWidget(mark)
    brand = QVBoxLayout()
    brand.setSpacing(1)
    brand.addWidget(label("LocalCast", "brand"))
    brand.addWidget(label("Vídeos locais no seu Chromecast", "muted"))
    header.addLayout(brand)
    header.addStretch()
    self.movie_settings_button = QPushButton("Configurar filmes")
    self.movie_settings_button.clicked.connect(self.configure_movies)
    header.addWidget(self.movie_settings_button)
    layout.addLayout(header)

    middle = QHBoxLayout()
    middle.setSpacing(16)
    controls = QWidget()
    controls.setObjectName("scrollContent")
    controls.setMinimumWidth(430)
    column = QVBoxLayout(controls)
    column.setContentsMargins(0, 0, 4, 0)
    column.setSpacing(12)
    device, content = card("Chromecast")
    row = QHBoxLayout()
    self.device_box = DarkComboBox()
    self.device_box.setPlaceholderText("Busque um Chromecast na sua rede")
    self.device_box.setAccessibleName("Chromecast selecionado")
    self.device_box.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    self.device_box.setMinimumContentsLength(14)
    self.search = QPushButton("Buscar Chromecast")
    self.search.clicked.connect(self.discover)
    row.addWidget(self.device_box, 1)
    row.addWidget(self.search)
    self.connect_button = QPushButton("Conectar")
    self.connect_button.setToolTip(
        "Mostra a tela de espera do LocalCast antes de escolher um vídeo."
    )
    self.connect_button.clicked.connect(self.connect_standby)
    content.addLayout(row)
    self.network_toggle = QToolButton()
    self.network_toggle.setObjectName("disclosure")
    self.network_toggle.setText("Rede e conexão")
    self.network_toggle.setCheckable(True)
    self.network_toggle.setArrowType(Qt.ArrowType.RightArrow)
    self.network_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    network_row = QHBoxLayout()
    network_row.addWidget(self.network_toggle)
    network_row.addStretch()
    network_row.addWidget(self.connect_button)
    content.addLayout(network_row)
    self.network_fields = QWidget()
    network_form = QFormLayout(self.network_fields)
    network_form.setContentsMargins(0, 4, 0, 0)
    self.known_host = QLineEdit()
    self.known_host.setPlaceholderText("Opcional: 192.168.1.50")
    self.lan_ip = QLineEdit()
    self.lan_ip.setPlaceholderText("Automático; informe o IP do PC se necessário")
    network_form.addRow("IP do Chromecast", self.known_host)
    network_form.addRow("IP LAN do PC", self.lan_ip)
    content.addWidget(self.network_fields)
    self.network_fields.hide()
    self.network_toggle.toggled.connect(self.network_fields.setVisible)
    self.network_toggle.toggled.connect(
        lambda checked: self.network_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
    )
    column.addWidget(device)

    file_card, content = card("Arquivo")
    row = QHBoxLayout()
    file_heading = content.itemAt(0).widget()
    content.removeWidget(file_heading)
    self.open_button = QPushButton("Abrir MP4 / MKV")
    self.open_button.clicked.connect(self.open_file)
    self.file_label = label("Nenhum arquivo selecionado", "", True)
    row.addWidget(file_heading, 1)
    row.addWidget(self.open_button)
    content.addLayout(row)
    content.addWidget(self.file_label)
    self.media_label = label("Escolha um vídeo para transmitir pela sua rede.", "muted", True)
    content.addWidget(self.media_label)
    column.addWidget(file_card)

    options, content = card("Conversão e faixas")
    form = QFormLayout()
    form.setVerticalSpacing(10)
    self.resolution = DarkComboBox()
    self.resolution.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    self.resolution.setMinimumContentsLength(20)
    self.resolution.addItem("Automática — até 1080p / 30 fps", 1080)
    self.resolution.addItem("Automática — até 720p / 30 fps (menos CPU)", 720)
    self.resolution.addItem("Original, sem conversão (experimental)", 0)
    self.resolution.setAccessibleName("Modo de conversão")
    self.resolution.setToolTip(
        "A mudança de conversão vale na próxima transmissão, ao clicar Transmitir."
    )
    self.audio_box = DarkComboBox()
    self.audio_box.setAccessibleName("Faixa de áudio")
    self.subtitle_box = DarkComboBox()
    self.subtitle_box.setAccessibleName("Faixa de legenda")
    for combo in (self.audio_box, self.subtitle_box):
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(20)
    self.audio_box.addItem("Abra um arquivo para escolher", -1)
    self.subtitle_box.addItem("Sem legenda", None)
    form.addRow("&Conversão", self.resolution)
    form.addRow("&Áudio", self.audio_box)
    form.addRow("&Legenda", self.subtitle_box)
    content.addLayout(form)
    self.force_hls = QCheckBox("Forçar HLS, inclusive em MP4 compatível")
    self.force_hls.setToolTip(
        "Mantém o teste de compatibilidade HLS. Original envia sem conversão."
    )
    content.addWidget(self.force_hls)
    self.conversion_hint = label("", "muted", True)
    content.addWidget(self.conversion_hint)
    self.tracks_hint = label("Escolha as faixas antes de transmitir.", "muted", True)
    content.addWidget(self.tracks_hint)
    self.apply_tracks_button = QPushButton("Aplicar faixas")
    self.apply_tracks_button.setToolTip(
        "Recarrega o vídeo com as faixas escolhidas, mantendo a posição."
    )
    self.apply_tracks_button.clicked.connect(self.apply_tracks)
    content.addWidget(self.apply_tracks_button, 0, Qt.AlignmentFlag.AlignRight)
    self.audio_box.currentIndexChanged.connect(self._tracks_changed)
    self.subtitle_box.currentIndexChanged.connect(self._tracks_changed)
    self.resolution.currentIndexChanged.connect(self._conversion_changed)
    column.addWidget(options)
    column.addStretch()
    middle.addWidget(scroller(controls), 6)
    self.movie_panel = MoviePanel()
    self.movie_panel.setMinimumWidth(350)
    self.movie_panel.configure_requested.connect(self.configure_movies)
    self.movie_panel.correct_requested.connect(self.correct_movie)
    self.movie_panel.refresh_requested.connect(self.refresh_movie)
    middle.addWidget(scroller(self.movie_panel), 5)
    layout.addLayout(middle, 1)

    player = QFrame()
    player.setObjectName("player")
    content = QVBoxLayout(player)
    content.setContentsMargins(18, 14, 18, 14)
    content.setSpacing(12)
    self.slider = QSlider(Qt.Orientation.Horizontal)
    self.slider.setAccessibleName("Posição do vídeo")
    self.slider.setRange(0, 0)
    self.slider.sliderReleased.connect(lambda: self.seek(self.slider.value()))
    content.addWidget(self.slider)
    row = QHBoxLayout()
    row.setSpacing(8)
    self.cast_button = QPushButton("Transmitir")
    self.cast_button.setObjectName("primary")
    self.cast_button.setMinimumWidth(124)
    self.cast_button.clicked.connect(self.cast_file)
    self.play_button = QPushButton("Play")
    self.pause_button = QPushButton("Pause")
    self.stop_button = QPushButton("Parar")
    self.disconnect_button = QPushButton("Desconectar")
    self.disconnect_button.setToolTip("Encerra a sessão do LocalCast e libera o Chromecast.")
    self.play_button.clicked.connect(lambda: self.action("play"))
    self.pause_button.clicked.connect(lambda: self.action("pause"))
    self.stop_button.clicked.connect(lambda: self.task("stop", self.session.stop_to_standby))
    self.disconnect_button.clicked.connect(lambda: self.task("disconnect", self.session.disconnect))
    for button in (
        self.cast_button,
        self.play_button,
        self.pause_button,
        self.stop_button,
        self.disconnect_button,
    ):
        row.addWidget(button)
    row.addStretch()
    self.time_label = label("00:00:00 / 00:00:00")
    row.addWidget(self.time_label)
    self.seek_seconds = DarkSpinBox()
    self.seek_seconds.setRange(0, 0)
    self.seek_seconds.setSuffix(" s")
    self.seek_seconds.setFixedWidth(84)
    self.seek_button = QPushButton("Ir para")
    self.seek_button.clicked.connect(lambda: self.seek(self.seek_seconds.value()))
    row.addWidget(self.seek_seconds)
    row.addWidget(self.seek_button)
    content.addLayout(row)
    self.state_label = label("Pronto", "muted", True)
    content.addWidget(self.state_label)
    layout.addWidget(player)

    self.debug_toggle = QToolButton()
    self.debug_toggle.setText("Depuração")
    self.debug_toggle.setCheckable(True)
    self.debug_toggle.setArrowType(Qt.ArrowType.RightArrow)
    self.debug_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    footer = QHBoxLayout()
    footer.addWidget(self.debug_toggle)
    footer.addStretch()
    footer.addWidget(label("Ao fechar, o LocalCast desconecta do Chromecast.", "muted"))
    footer.addStretch()
    self.author_signature = label("By " + __author__, "signature")
    self.author_signature.setAccessibleName("By " + __author__)
    self.author_signature.setToolTip("By " + __author__)
    signature = QPixmap(str(asset_path("assinatura-fagner-lemes.png")))
    if not signature.isNull():
        self.author_signature.setPixmap(
            signature.scaled(
                150,
                37,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.author_signature.setFixedSize(150, 37)
    footer.addWidget(self.author_signature)
    layout.addLayout(footer)
    self.debug_panel = QFrame()
    self.debug_panel.setObjectName("debugPanel")
    debug = QVBoxLayout(self.debug_panel)
    debug.setContentsMargins(16, 14, 16, 14)
    self.notes = QPlainTextEdit()
    self.notes.setReadOnly(True)
    self.notes.setMaximumBlockCount(300)
    self.notes.setMinimumHeight(120)
    self.notes.setMaximumHeight(170)
    self.notes.setAccessibleName("Mensagens de depuração")
    debug.addWidget(self.notes)
    self.report_button = QPushButton("Salvar diagnóstico JSON")
    self.report_button.clicked.connect(self.save_report)
    debug.addWidget(self.report_button, 0, Qt.AlignmentFlag.AlignRight)
    layout.addWidget(self.debug_panel)
    self.debug_panel.hide()
    self.debug_toggle.toggled.connect(self.debug_panel.setVisible)
    self.debug_toggle.toggled.connect(
        lambda checked: self.debug_toggle.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )
    )
