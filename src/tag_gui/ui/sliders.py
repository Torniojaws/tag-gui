from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSlider

from .styles import PROGRESS_TEXT_ON_FILL, PROGRESS_TEXT_ON_REST


class SeekSlider(QSlider):
    """Click-anywhere slider that draws the elapsed/total text across its middle."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def set_text(self, text: str):
        if text != self._text:
            self._text = text
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            span = self.maximum() - self.minimum()
            value = self.minimum() + (span * event.pos().x()) / max(1, self.width())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._text:
            return
        span = self.maximum() - self.minimum()
        filled = 0 if span <= 0 else round(self.width() * (self.value() - self.minimum()) / span)
        painter = QPainter(self)
        # Drawn twice and clipped, so the text stays readable over both halves of the bar.
        for color, clip in (
            (PROGRESS_TEXT_ON_FILL, QRect(0, 0, filled, self.height())),
            (PROGRESS_TEXT_ON_REST, QRect(filled, 0, self.width() - filled, self.height())),
        ):
            painter.setPen(QColor(color))
            painter.setClipRect(clip)
            painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()
