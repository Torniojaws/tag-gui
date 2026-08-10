from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

from .constants import ICON_SIZES


def note_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = QFont("Segoe UI Symbol")
    font.setPixelSize(int(size * 0.9))
    painter.setFont(font)
    painter.setPen(QColor("#2d6cdf"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "\u266a")
    painter.end()
    return pixmap


def note_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(note_pixmap(size))
    return icon
