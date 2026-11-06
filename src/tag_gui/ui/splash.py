from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..constants import APP_TITLE, APP_VERSION
from .icons import note_pixmap


class Splash(QWidget):
    """Startup window with a progress bar, shown while playlists load."""

    def __init__(self):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint)
        self.setFixedSize(380, 236)

        icon = QLabel()
        icon.setPixmap(note_pixmap(64))
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel(APP_TITLE)
        title_font = title.font()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)

        self.version = QLabel(f"Version {APP_VERSION}")
        self.version.setAlignment(Qt.AlignCenter)
        self.version.setEnabled(False)

        self.status = QLabel("Starting...")
        self.status.setAlignment(Qt.AlignCenter)

        self._message = ""
        self._total = 0

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(icon)
        layout.addWidget(title)
        layout.addWidget(self.version)
        layout.addWidget(self.status)
        layout.addWidget(self.bar)

    def show_centered(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.move(screen.availableGeometry().center() - self.rect().center())
        self.show()
        # Paint now instead of waiting for the event loop, which only starts after loading.
        QApplication.processEvents()
        self.repaint()

    def begin(self, message: str, total: int):
        self._message = message
        self._total = total
        self.status.setText(message)
        self.bar.setRange(0, max(0, total))
        self.bar.setValue(0)
        self.bar.show()
        QApplication.processEvents()

    def update_progress(self, value: int):
        self.bar.setValue(value)
        if self._total:
            self.status.setText(f"{self._message} {value} / {self._total}")
        QApplication.processEvents()

    def end(self):
        self.status.setText("Starting...")
        self.bar.hide()
        QApplication.processEvents()
