import sys

from PySide6.QtWidgets import QApplication

from .constants import APP_ID
from .icons import note_icon
from .main_window import MainWindow


def main():
    if sys.platform == "win32":
        # Without an explicit AppUserModelID Windows shows the host python.exe icon in the taskbar.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setWindowIcon(note_icon())
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    return app.exec()
