from PySide6.QtWidgets import QApplication

from .styles import TRANSPORT_BUTTON_RANGE, TRANSPORT_BUTTON_SCALE

FALLBACK_SCREEN_HEIGHT = 900


def screen_geometry():
    screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def transport_button_size() -> int:
    geometry = screen_geometry()
    height = geometry.height() if geometry else FALLBACK_SCREEN_HEIGHT
    smallest, largest = TRANSPORT_BUTTON_RANGE
    return max(smallest, min(largest, round(height * TRANSPORT_BUTTON_SCALE)))
