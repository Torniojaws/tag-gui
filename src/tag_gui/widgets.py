from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QSlider, QTableWidget, QTableWidgetItem

from .constants import AUDIO_EXTENSIONS


class SeekSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            value = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / max(1, self.width())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)


class TagCheckItem(QTableWidgetItem):
    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            return int(self.checkState() == Qt.Checked) < int(other.checkState() == Qt.Checked)
        return super().__lt__(other)


class PlaylistTable(QTableWidget):
    def __init__(self, on_files_dropped, on_delete_pressed, parent=None):
        super().__init__(parent)
        self.on_files_dropped = on_files_dropped
        self.on_delete_pressed = on_delete_pressed
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and not event.modifiers():
            self.on_delete_pressed()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            local = Path(url.toLocalFile())
            if local.is_dir() or local.suffix.lower() in AUDIO_EXTENSIONS:
                paths.append(str(local))
        if paths:
            self.on_files_dropped(paths)
            event.acceptProposedAction()
        else:
            event.ignore()
