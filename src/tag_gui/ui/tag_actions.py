"""The custom tag row, the standard tag editor and writing tags back to disk."""

from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QMenu, QMessageBox, QPushButton

from ..constants import DEFAULT_COLUMNS
from ..core.tags import parse_custom_tags, set_custom_tag, set_standard_tags
from .dialogs import StandardTagsDialog
from .styles import ROW_MARGIN
from .table_fill import TAG_NAME_ROLE, selected_tracks
from .window_base import WindowContext

MAX_REPORTED_FAILURES = 10


class TagActionsMixin(WindowContext):
    def _build_tags_row(self) -> QHBoxLayout:
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Custom checkbox tags (comma separated)")
        apply_button = QPushButton("Apply Tags")
        apply_button.clicked.connect(self.apply_custom_tags)

        row = QHBoxLayout()
        row.setContentsMargins(ROW_MARGIN, ROW_MARGIN, ROW_MARGIN, 0)
        row.addWidget(self.tags_input)
        row.addWidget(apply_button)
        return row

    def load_custom_tags(self):
        if self.custom_tags_file.exists():
            self.custom_tags = parse_custom_tags(self.custom_tags_file.read_text(encoding="utf-8"))
        else:
            self.custom_tags = []
        self.tags_input.setText(", ".join(self.custom_tags))

    def save_custom_tags(self):
        self.custom_tags_file.write_text(",".join(self.custom_tags), encoding="utf-8")

    def apply_custom_tags(self):
        self.custom_tags = parse_custom_tags(self.tags_input.text())
        self.save_custom_tags()
        for index, playlist in enumerate(self.playlists):
            self.populate_table(self.tabs.widget(index), playlist)
        self.save_state()

    def on_table_context_menu(self, pos):
        table = self.current_table()
        menu = QMenu(self)
        edit_action = menu.addAction("Edit tags...")
        edit_action.setEnabled(bool(selected_tracks(table)))
        if menu.exec(table.mapToGlobal(pos)) is edit_action:
            self.edit_selected_tags()

    def edit_selected_tags(self):
        table = self.current_table()
        tracks = selected_tracks(table)
        if not tracks:
            return
        fields = [self.metadata.get(track, self.custom_tags).fields for track in tracks]
        dialog = StandardTagsDialog(fields, self)
        if dialog.exec() != QDialog.Accepted:
            return
        values = dialog.changed_values()
        if not values:
            return

        failures = []
        updated = []
        for track in tracks:
            try:
                set_standard_tags(Path(track), values)
            except Exception as exc:
                failures.append(f"{Path(track).name}: {exc}")
            else:
                self.metadata.discard(track)
                updated.append(track)
        self.refresh_tracks(table, updated)
        if failures:
            self.report_failures(failures)

    def report_failures(self, failures: List[str]):
        shown = "\n".join(failures[:MAX_REPORTED_FAILURES])
        extra = len(failures) - MAX_REPORTED_FAILURES
        more = "" if extra <= 0 else f"\n...and {extra} more"
        QMessageBox.warning(self, "Tag write failed", f"Could not update:\n{shown}{more}")

    def on_item_changed(self, item):
        if self._updating_table or item.column() < len(DEFAULT_COLUMNS):
            return
        track = item.data(Qt.UserRole)
        tag = item.data(TAG_NAME_ROLE)
        if not track or not tag:
            return

        checked = item.checkState() == Qt.Checked
        try:
            set_custom_tag(Path(track), tag, checked)
        except Exception as exc:
            QMessageBox.warning(
                self, "Tag write failed", f"Could not update tag '{tag}' for file:\n{track}\n\n{exc}"
            )
            self._updating_table = True
            try:
                item.setCheckState(Qt.Unchecked if checked else Qt.Checked)
            finally:
                self._updating_table = False
            return
        self.metadata.update_tag_state(track, tag, checked)
