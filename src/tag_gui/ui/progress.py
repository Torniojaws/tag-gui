"""Progress reporting for the slow tag-reading passes."""

from typing import Callable, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from ..constants import PROGRESS_THRESHOLD

Reporter = Tuple[Callable[[int], None], Callable[[], None]]


def progress_reporter(parent: QWidget, splash, label: str, total: int) -> Reporter:
    """Report progress on the splash while starting, in a modal dialog afterwards."""
    if splash is not None:
        splash.begin(label, total)
        return splash.update_progress, splash.end
    if total <= PROGRESS_THRESHOLD:
        return (lambda _value: None), (lambda: None)

    dialog = QProgressDialog(f"{label}...", None, 0, total, parent)
    dialog.setWindowTitle("Loading playlist")
    dialog.setWindowModality(Qt.WindowModal)
    dialog.setMinimumDuration(300)

    def update(value: int):
        dialog.setValue(value)
        QApplication.processEvents()

    return update, dialog.close
