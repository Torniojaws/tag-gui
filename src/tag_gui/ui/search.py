"""The Ctrl+F filter bar that narrows the current playlist down to matching rows."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from .styles import ROW_MARGIN
from .window_base import WindowContext


class SearchMixin(WindowContext):
    def _build_search_row(self) -> QWidget:
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by artist, song or album (Ctrl+F to close)")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_count = QLabel()

        self.search_row = QWidget()
        layout = QHBoxLayout(self.search_row)
        layout.setContentsMargins(ROW_MARGIN, ROW_MARGIN, ROW_MARGIN, 0)
        layout.addWidget(self.search_input)
        layout.addWidget(self.search_count)
        self.search_row.hide()

        QShortcut(QKeySequence.Find, self, self.toggle_search)
        QShortcut(QKeySequence(Qt.Key_Escape), self.search_input, self.close_search, Qt.WidgetShortcut)
        return self.search_row

    def toggle_search(self):
        if self.search_row.isVisible():
            self.close_search()
        else:
            self.open_search()

    def open_search(self):
        self.search_row.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def close_search(self):
        """Hide the bar and bring back the full list in every playlist."""
        self.search_row.hide()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        for index in range(self.tabs.count()):
            self.tabs.widget(index).set_filter("")
        table = self.current_table()
        if table is not None:
            table.setFocus()

    def on_search_text_changed(self, text: str):
        table = self.current_table()
        if table is not None:
            table.set_filter(text)
        self.update_search_count()

    def apply_search_to_current(self):
        """A playlist switched to while filtering shows the same search."""
        table = self.current_table()
        if table is not None:
            table.set_filter(self.search_input.text())
        self.update_search_count()

    def update_search_count(self):
        table = self.current_table()
        if table is None or not self.search_input.text().strip():
            self.search_count.clear()
            return
        self.search_count.setText(f"{table.visible_rows} of {table.rowCount()}")
