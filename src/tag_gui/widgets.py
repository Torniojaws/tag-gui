from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QLineEdit,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
)

from .constants import (
    ALBUM_COLUMN,
    ALBUM_TINT_DARK,
    ALBUM_TINT_LIGHT,
    AUDIO_EXTENSIONS,
    PROGRESS_TEXT_ON_FILL,
    PROGRESS_TEXT_ON_REST,
)


def is_checked(index) -> bool:
    # CheckStateRole comes back as a plain int, which never compares equal to Qt.Checked.
    state = index.data(Qt.CheckStateRole)
    return state is not None and Qt.CheckState(state) == Qt.Checked


class PlaylistTabBar(QTabBar):
    """Tab bar whose labels can be renamed in place."""

    name_edited = Signal(int, str)
    middle_clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editing_index = -1
        self._editor = QLineEdit(self)
        self._editor.hide()
        self._editor.installEventFilter(self)
        self._editor.editingFinished.connect(self.commit_edit)

    def edit_tab(self, index: int):
        if index < 0:
            return
        self._editing_index = index
        self._editor.setText(self.tabText(index))
        self._editor.setGeometry(self.tabRect(index))
        self._editor.selectAll()
        self._editor.show()
        self._editor.setFocus()

    def commit_edit(self):
        if self._editing_index < 0:
            return
        index, self._editing_index = self._editing_index, -1
        self._editor.hide()
        name = self._editor.text().strip()
        if name and name != self.tabText(index):
            self.name_edited.emit(index, name)

    def cancel_edit(self):
        self._editing_index = -1
        self._editor.hide()

    def eventFilter(self, watched, event):
        if watched is self._editor and event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.cancel_edit()
            return True
        return super().eventFilter(watched, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index != -1:
                self.middle_clicked.emit(index)
                return
        super().mouseReleaseEvent(event)


class PlaylistTabs(QTabWidget):
    """The strip right of the tabs belongs to the tab widget, so the tab bar never sees
    double-clicks there."""

    empty_double_clicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.empty_double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class CenteredCheckDelegate(QStyledItemDelegate):
    """Qt always lays the check indicator out on the left, so draw it centered instead."""

    def indicator_rect(self, option, widget) -> QRect:
        style = widget.style() if widget else QApplication.style()
        rect = QRect(
            0,
            0,
            style.pixelMetric(QStyle.PM_IndicatorWidth, option, widget),
            style.pixelMetric(QStyle.PM_IndicatorHeight, option, widget),
        )
        rect.moveCenter(option.rect.center())
        return rect

    def paint(self, painter, option, index):
        if not index.flags() & Qt.ItemIsUserCheckable:
            super().paint(painter, option, index)
            return

        view_option = QStyleOptionViewItem(option)
        self.initStyleOption(view_option, index)
        view_option.text = ""
        view_option.features &= ~QStyleOptionViewItem.HasCheckIndicator
        widget = view_option.widget
        style = widget.style() if widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, view_option, painter, widget)

        button = QStyleOptionButton()
        button.rect = self.indicator_rect(option, widget)
        button.state = QStyle.State_Enabled
        button.state |= QStyle.State_On if is_checked(index) else QStyle.State_Off
        style.drawPrimitive(QStyle.PE_IndicatorCheckBox, button, painter, widget)

    def editorEvent(self, event, model, option, index):
        if not index.flags() & Qt.ItemIsUserCheckable:
            return super().editorEvent(event, model, option, index)
        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
            if self.indicator_rect(option, option.widget).contains(event.position().toPoint()):
                new_state = Qt.Unchecked if is_checked(index) else Qt.Checked
                return model.setData(index, new_state, Qt.CheckStateRole)
        return False


class SeekSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._text = ""

    def set_text(self, text: str):
        if text != self._text:
            self._text = text
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            value = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / max(1, self.width())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._text:
            return
        span = self.maximum() - self.minimum()
        filled = 0 if span <= 0 else round(self.width() * (self.value() - self.minimum()) / span)
        painter = QPainter(self)
        # Drawn twice and clipped, so the text stays readable over both halves of the bar.
        for color, clip in (
            (PROGRESS_TEXT_ON_FILL, QRect(0, 0, filled, self.height())),
            (PROGRESS_TEXT_ON_REST, QRect(filled, 0, self.width() - filled, self.height())),
        ):
            painter.setPen(QColor(color))
            painter.setClipRect(clip)
            painter.drawText(self.rect(), Qt.AlignCenter, self._text)
        painter.end()


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
