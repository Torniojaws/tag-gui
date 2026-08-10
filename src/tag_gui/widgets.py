from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QAbstractItemView, QSlider, QTableWidget, QTableWidgetItem

from .constants import ALBUM_COLUMN, ALBUM_TINT_DARK, ALBUM_TINT_LIGHT, AUDIO_EXTENSIONS


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

        # Sorting is driven from sectionClicked instead of setSortingEnabled so that a
        # newly clicked column starts descending, putting checked tags on top.
        self._sort_column = -1
        self._sort_order = Qt.DescendingOrder
        header = self.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.sectionClicked.connect(self.sort_by_column)

    def sort_by_column(self, column: int):
        if column == self._sort_column and self._sort_order == Qt.DescendingOrder:
            order = Qt.AscendingOrder
        else:
            order = Qt.DescendingOrder
        self._sort_column = column
        self._sort_order = order
        self.horizontalHeader().setSortIndicator(column, order)
        self.sortItems(column, order)
        self.apply_album_colors()
        self.scrollToTop()

    def reapply_sort(self):
        if self._sort_column >= 0:
            self.sortItems(self._sort_column, self._sort_order)

    def apply_album_colors(self):
        """Shade consecutive rows of one album alike, flipping shade at every album change."""
        base = self.palette().base().color()
        tint = ALBUM_TINT_LIGHT if base.lightness() > 128 else ALBUM_TINT_DARK
        brushes = (QBrush(base), QBrush(QColor(*tint)))
        shade = 0
        previous = None
        # Painting backgrounds would otherwise emit itemChanged for every custom tag cell.
        self.blockSignals(True)
        try:
            for row in range(self.rowCount()):
                album_item = self.item(row, ALBUM_COLUMN)
                album = album_item.text() if album_item else ""
                if previous is not None and album != previous:
                    shade = 1 - shade
                previous = album
                for col in range(self.columnCount()):
                    cell = self.item(row, col)
                    if cell:
                        cell.setBackground(brushes[shade])
        finally:
            self.blockSignals(False)

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
