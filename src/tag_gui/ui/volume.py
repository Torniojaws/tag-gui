from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSlider, QWidget

from .icons import speaker_icon
from .styles import (
    MUTE_BUTTON_SIZE,
    MUTE_ICON_COLOR,
    MUTE_ICON_SIZE,
    VOLUME_DEFAULT,
    VOLUME_SLIDER_WIDTH,
)

WHEEL_STEP = 5
PAGE_STEP = 10


class VolumeControls(QWidget):
    """Volume slider plus a mute toggle that works independently of it."""

    volume_changed = Signal(int)
    mute_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mute_btn = QPushButton()
        self.mute_btn.setCheckable(True)
        self.mute_btn.setToolTip("Mute, independent of the volume slider")
        self.mute_btn.setFixedSize(MUTE_BUTTON_SIZE, MUTE_BUTTON_SIZE)
        self.mute_btn.setIconSize(QSize(MUTE_ICON_SIZE, MUTE_ICON_SIZE))
        self.mute_btn.toggled.connect(self._on_mute_toggled)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setFixedWidth(VOLUME_SLIDER_WIDTH)
        self.slider.setSingleStep(WHEEL_STEP)
        self.slider.setPageStep(PAGE_STEP)
        self.slider.valueChanged.connect(self._on_value_changed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 0, Qt.AlignVCenter)
        layout.addWidget(self.mute_btn, 0, Qt.AlignVCenter)

        self._update_icon(False)
        self.slider.setValue(VOLUME_DEFAULT)

    def _on_value_changed(self, value: int):
        self.slider.setToolTip(f"Volume {value}%")
        self.volume_changed.emit(value)

    def _on_mute_toggled(self, muted: bool):
        self._update_icon(muted)
        self.mute_changed.emit(muted)

    def _update_icon(self, muted: bool):
        color = QColor(MUTE_ICON_COLOR) if muted else self.palette().windowText().color()
        self.mute_btn.setIcon(speaker_icon(MUTE_ICON_SIZE, color))
