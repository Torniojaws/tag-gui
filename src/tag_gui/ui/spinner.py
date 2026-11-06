"""A small animated busy indicator."""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

from .styles import SPINNER_INTERVAL_MS, SPINNER_SIZE


class Spinner(QWidget):
    """A rotating arc, drawn in the palette's highlight color."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SPINNER_SIZE, SPINNER_SIZE)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(SPINNER_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)
        self.hide()

    def start(self):
        self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def is_spinning(self) -> bool:
        return self._timer.isActive()

    def _advance(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.palette().highlight().color(), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        # Qt angles run counter-clockwise in 1/16 degrees; subtracting turns the arc clockwise.
        painter.drawArc(self.rect().adjusted(2, 2, -2, -2), -self._angle * 16, 270 * 16)
