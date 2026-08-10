import sys

from PySide6.QtWidgets import QApplication

from .constants import APP_ID
from .splash import Splash


def main():
    if sys.platform == "win32":
        # Without an explicit AppUserModelID Windows shows the host python.exe icon in the taskbar.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    splash = Splash()
    splash.show_centered()

    # Imported here so the splash is on screen before mutagen and QtMultimedia load.
    from .icons import note_icon
    from .main_window import MainWindow

    app.setWindowIcon(note_icon())
    win = MainWindow(splash=splash)
    win.resize(1200, 700)
    win.show()
    splash.close()
    return app.exec()
