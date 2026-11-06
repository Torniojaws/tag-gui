from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget

from .sizing import transport_button_size
from .styles import (
    NEXT_BUTTON_GLYPH,
    PAUSE_BUTTON_GLYPH,
    PAUSE_BUTTON_STYLE,
    PLAY_BUTTON_GLYPH,
    PLAY_BUTTON_STYLE,
    PREV_BUTTON_GLYPH,
    STOP_BUTTON_GLYPH,
    STOP_BUTTON_STYLE,
)

GLYPH_SCALE = 0.4


class TransportBar(QWidget):
    """Square previous/play/stop/next buttons and the shuffle toggle."""

    previous_clicked = Signal()
    play_pause_clicked = Signal()
    stop_clicked = Signal()
    next_clicked = Signal()
    shuffle_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prev_btn = QPushButton(PREV_BUTTON_GLYPH)
        self.play_btn = QPushButton(PLAY_BUTTON_GLYPH)
        self.stop_btn = QPushButton(STOP_BUTTON_GLYPH)
        self.next_btn = QPushButton(NEXT_BUTTON_GLYPH)

        size = transport_button_size()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for button, tooltip, signal in (
            (self.prev_btn, "Previous", self.previous_clicked),
            (self.play_btn, "Play", self.play_pause_clicked),
            (self.stop_btn, "Stop", self.stop_clicked),
            (self.next_btn, "Next", self.next_clicked),
        ):
            button.setToolTip(tooltip)
            button.setFixedSize(size, size)
            font = button.font()
            font.setPixelSize(round(size * GLYPH_SCALE))
            button.setFont(font)
            button.clicked.connect(signal.emit)
            layout.addWidget(button, 0, Qt.AlignVCenter)

        self.play_btn.setStyleSheet(PLAY_BUTTON_STYLE)
        self.stop_btn.setStyleSheet(STOP_BUTTON_STYLE)

        self.shuffle_box = QCheckBox("Shuffle")
        self.shuffle_box.setToolTip(
            "Play in random order, avoiding the artists, albums and songs of the last 10 tracks"
        )
        self.shuffle_box.toggled.connect(self.shuffle_toggled.emit)
        layout.addSpacing(4)
        layout.addWidget(self.shuffle_box, 0, Qt.AlignVCenter)

    def set_shuffle(self, enabled: bool):
        """Reflect a loaded setting without emitting shuffle_toggled."""
        self.shuffle_box.blockSignals(True)
        self.shuffle_box.setChecked(enabled)
        self.shuffle_box.blockSignals(False)

    def set_playing(self, playing: bool):
        self.play_btn.setText(PAUSE_BUTTON_GLYPH if playing else PLAY_BUTTON_GLYPH)
        self.play_btn.setToolTip("Pause" if playing else "Play")
        self.play_btn.setStyleSheet(PAUSE_BUTTON_STYLE if playing else PLAY_BUTTON_STYLE)
