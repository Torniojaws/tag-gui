from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPolygonF

from ..constants import ICON_SIZES


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


def speaker_pixmap(size: int, color: QColor) -> QPixmap:
    """Drawn rather than taken from a font, since speaker glyphs render as colour emoji."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    unit = size / 16

    painter.setPen(Qt.NoPen)
    painter.setBrush(color)
    painter.drawRect(QRectF(2 * unit, 6 * unit, 3 * unit, 4 * unit))
    painter.drawPolygon(
        QPolygonF(
            [
                QPointF(5 * unit, 6 * unit),
                QPointF(8 * unit, 3 * unit),
                QPointF(8 * unit, 13 * unit),
                QPointF(5 * unit, 10 * unit),
            ]
        )
    )

    painter.setBrush(Qt.NoBrush)
    painter.setPen(QPen(color, max(1.0, unit), Qt.SolidLine, Qt.RoundCap))
    painter.drawArc(QRectF(8 * unit, 5 * unit, 4 * unit, 6 * unit), -70 * 16, 140 * 16)
    painter.drawArc(QRectF(8 * unit, 3 * unit, 7 * unit, 10 * unit), -70 * 16, 140 * 16)
    painter.end()
    return pixmap


def speaker_icon(size: int, color: QColor) -> QIcon:
    return QIcon(speaker_pixmap(size, color))
