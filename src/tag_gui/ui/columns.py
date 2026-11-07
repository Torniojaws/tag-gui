"""One column layout (order and widths) shared by every playlist and kept in settings."""

from PySide6.QtCore import QTimer

from ..core.settings import save_settings
from .table import PlaylistTable
from .window_base import WindowContext

# A drag resizes a column pixel by pixel; write the settings once it has settled.
SAVE_DELAY_MS = 500


class ColumnsMixin(WindowContext):
    def _build_column_sync(self):
        self._column_save_timer = QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.setInterval(SAVE_DELAY_MS)
        self._column_save_timer.timeout.connect(self.save_column_layout)

    def connect_column_sync(self, table: PlaylistTable):
        table.columns_moved.connect(lambda: self.on_columns_moved(table))
        table.column_resized.connect(self.on_column_resized)

    def apply_column_layout(self, table: PlaylistTable):
        table.apply_column_layout(self.settings.column_order, self.settings.column_widths)

    def on_columns_moved(self, source: PlaylistTable):
        self.settings.column_order = source.column_order()
        self._sync_columns(source)

    def on_column_resized(self, name: str, width: int):
        self.settings.column_widths[name] = width
        self._sync_columns(None)

    def _sync_columns(self, source):
        for index in range(self.tabs.count()):
            table = self.tabs.widget(index)
            if table is not source:
                self.apply_column_layout(table)
        self._column_save_timer.start()

    def save_column_layout(self):
        self._column_save_timer.stop()
        save_settings(self.settings_file, self.settings)
