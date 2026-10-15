"""LocalCast dark cinema theme; native controls, visible focus, no decorative animation."""

import os

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QComboBox, QSpinBox, QStyle, QStyleOptionSpinBox

STYLE = """
QWidget { color: #f3f3f5; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QDialog, QWidget#root, QWidget#scrollContent { background: #101113; }
QScrollArea { border: none; background: transparent; }
QFrame#card, QFrame#moviePanel, QFrame#player, QFrame#debugPanel {
  background: #1b1d21; border: 1px solid #292c32; border-radius: 16px;
}
QLabel { background: transparent; }
QLabel#brand { font-size: 25px; font-weight: 700; }
QLabel#brandMark { background: #f5c518; color: #111214; border-radius: 10px; font-size: 18px; font-weight: 800; }
QLabel#brandLogo { background: transparent; padding: 0; }
QLabel#sectionTitle { font-size: 16px; font-weight: 600; }
QLabel#movieTitle { font-size: 24px; font-weight: 700; }
QLabel#muted { color: #aeb3bd; font-size: 12px; }
QLabel#rating { color: #f5c518; font-size: 22px; font-weight: 700; }
QLabel#signature { color: #d2d5dc; font-size: 12px; font-weight: 600; }
QLabel#badge { color: #c6cbd4; background: #262930; border-radius: 6px; padding: 5px 9px; font-size: 11px; }
QPushButton, QToolButton {
  background: #292c32; border: 1px solid #3b4049; border-radius: 9px;
  padding: 9px 14px; color: #f3f3f5; font-weight: 600; min-height: 18px;
}
QPushButton:hover, QToolButton:hover { background: #353941; border-color: #6f7683; }
QPushButton:pressed, QToolButton:pressed, QToolButton:checked { background: #414650; }
QPushButton:focus, QToolButton:focus { border: 1px solid #f5c518; }
QPushButton:disabled, QToolButton:disabled { color: #727986; background: #22252b; border-color: #30343c; }
QPushButton#primary { background: #f5c518; color: #151515; border: 1px solid #f5c518; }
QPushButton#primary:hover { background: #ffdb50; border-color: #ffdb50; }
QPushButton#primary:pressed { background: #d9aa0c; }
QPushButton#primary:disabled { background: #544a26; border-color: #544a26; color: #a79a65; }
QPushButton#link { background: transparent; border: none; color: #e3c15a; padding: 4px 0px; text-align: left; }
QPushButton#link:hover { color: #ffdf72; }
QLineEdit, QComboBox, QSpinBox {
  background: #111317; border: 1px solid #3a3e47; border-radius: 8px;
  padding: 8px 10px; min-height: 18px; selection-background-color: #f5c518; selection-color: #111;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #f5c518; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled { color: #707783; background: #202329; border-color: #30343b; }
QComboBox { padding-right: 30px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 27px; border: none; }
QComboBox QAbstractItemView { background: #24272d; color: #f3f3f5; selection-background-color: #4c4222; selection-color: #fff; padding: 5px; border: 1px solid #626873; }
QCheckBox { color: #c6cbd4; spacing: 8px; font-size: 12px; }
QCheckBox:disabled { color: #717985; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #687180; border-radius: 4px; background: #15171b; }
QCheckBox::indicator:checked { background: #f5c518; border-color: #f5c518; }
QPlainTextEdit { background: #111317; color: #c9ced7; border: 1px solid #343943; border-radius: 8px; padding: 9px; selection-background-color: #544824; }
QSlider::groove:horizontal { height: 5px; background: #414650; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #f5c518; border-radius: 2px; }
QSlider::handle:horizontal { background: #f5c518; border: 2px solid #f5c518; width: 12px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: #ffdf72; border-color: #ffdf72; }
QSlider::groove:horizontal:disabled { background: #34383f; }
QSlider::handle:horizontal:disabled { background: #6b717d; border-color: #6b717d; }
QScrollBar:vertical { background: #15171a; width: 9px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #4b515d; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QToolTip { background: #2c3037; color: #fff; border: 1px solid #727988; padding: 7px; }
QToolButton#disclosure { padding: 4px 6px; min-height: 14px; border: none; background: transparent; color: #b8bec8; }
QToolButton#disclosure:hover { background: #292c32; color: #fff; }
QToolButton#disclosure:focus { border: 1px solid #f5c518; }
"""


def paint_arrow(painter, x, y, down, enabled):
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#cbd0d8" if enabled else "#767e8a"), 1.7))
    sign = 1 if down else -1
    painter.drawPolyline(
        QPolygonF(
            [QPointF(x - 4, y - sign * 2), QPointF(x, y + sign * 2), QPointF(x + 4, y - sign * 2)]
        )
    )


class DarkComboBox(QComboBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        paint_arrow(painter, self.width() - 17, self.height() / 2, True, self.isEnabled())


class DarkSpinBox(QSpinBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        for control, down in (
            (QStyle.SubControl.SC_SpinBoxUp, False),
            (QStyle.SubControl.SC_SpinBoxDown, True),
        ):
            rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox, option, control, self
            )
            paint_arrow(painter, rect.center().x(), rect.center().y(), down, self.isEnabled())


def apply_theme():
    app = QApplication.instance()
    if not app:
        return
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    palette = QPalette()
    for role, color in (
        (QPalette.Window, "#101113"),
        (QPalette.WindowText, "#f3f3f5"),
        (QPalette.Base, "#111317"),
        (QPalette.AlternateBase, "#1b1d21"),
        (QPalette.Text, "#f3f3f5"),
        (QPalette.Button, "#292c32"),
        (QPalette.ButtonText, "#f3f3f5"),
        (QPalette.Highlight, "#f5c518"),
        (QPalette.HighlightedText, "#111214"),
        (QPalette.ToolTipBase, "#292c32"),
        (QPalette.ToolTipText, "#f3f3f5"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)


def window_chrome(window):
    if os.name != "nt" or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        return
    try:
        import ctypes
        from ctypes import wintypes

        setter = ctypes.windll.dwmapi.DwmSetWindowAttribute
        setter.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        setter.restype = ctypes.c_long
        for attribute, value in ((20, 1), (33, 2)):
            option = ctypes.c_int(value)
            setter(int(window.winId()), attribute, ctypes.byref(option), ctypes.sizeof(option))
    except (AttributeError, OSError):
        pass  # Older Windows keeps its native title bar/corner policy.
