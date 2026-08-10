from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QLineEdit, QTabBar, QTabWidget


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabBar(PlaylistTabBar())
        self.setMovable(True)
        self.setTabsClosable(True)
        self.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)

    def mouseDoubleClickEvent(self, event):
        self.empty_double_clicked.emit()
        super().mouseDoubleClickEvent(event)
