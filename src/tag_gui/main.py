import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from .constants import APP_ID, DESKTOP_ID
from .ui.splash import Splash


def main():
    if sys.platform == "win32":
        # Without an explicit AppUserModelID Windows shows the host python.exe icon in the taskbar.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    # The X11 window class comes from the application name; a fixed one lets panels match the
    # window to the menu entry, whatever the versioned executable is called.
    QApplication.setApplicationName(DESKTOP_ID)
    QApplication.setDesktopFileName(DESKTOP_ID)
    app = QApplication(sys.argv)
    splash = Splash()
    splash.show_centered()

    # Imported here so the splash is on screen before mutagen and QtMultimedia load.
    from .ui.desktop_integration import integrate
    from .ui.icons import note_icon
    from .ui.main_window import MainWindow

    app.setWindowIcon(note_icon())
    integrate()
    win = MainWindow(splash=splash)
    # Tear the window down inside the event loop; left to PySide's exit cleanup, its widget
    # tree is destroyed after parts of it are already gone and the process segfaults.
    win.setAttribute(Qt.WA_DeleteOnClose)
    win.resize(1200, 700)
    win.show()
    splash.close()
    return app.exec()
