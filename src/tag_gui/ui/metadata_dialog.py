"""Shows every tag of one file and lets the text values be edited, added or removed."""

from pathlib import Path
from typing import Callable, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core.file_metadata import ADD_FIELD_HINTS, FileMetadata, changed_fields

FIELD_COL, KEY_COL, VALUE_COL = range(3)
NEW_FIELD_LABEL = "(new field)"


class MetadataDialog(QDialog):
    """``save`` receives the changed fields and raises to keep the dialog open on failure."""

    def __init__(
        self,
        path: Path,
        metadata: FileMetadata,
        save: Callable[[Dict[str, List[str]]], None],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Metadata - {path.name}")
        self.resize(760, 560)
        self._metadata = metadata
        self._save = save
        self._editable_rows = set()

        info = QFormLayout()
        for label, value in metadata.info:
            text = QLabel(value)
            text.setTextInteractionFlags(Qt.TextSelectableByMouse)
            text.setWordWrap(True)
            info.addRow(f"{label}:", text)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Field", "Key", "Value"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(FIELD_COL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(KEY_COL, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(VALUE_COL, QHeaderView.Stretch)
        for entry in metadata.entries:
            self._add_row(entry.label, entry.key, entry.value, entry.editable)

        self.add_button = QPushButton("Add field...")
        self.remove_button = QPushButton("Remove field")
        self.add_button.clicked.connect(self.add_field)
        self.remove_button.clicked.connect(self.remove_selected)
        self.table.itemSelectionChanged.connect(self._update_remove_button)
        self._update_remove_button()
        edit_row = QHBoxLayout()
        edit_row.addWidget(self.add_button)
        edit_row.addWidget(self.remove_button)
        edit_row.addStretch(1)

        self.note = QLabel()
        self.note.setWordWrap(True)
        if metadata.can_add:
            self.note.setText(
                "Double-click a value to edit it. Grey fields, like pictures, cannot be edited "
                "here. Clearing a value removes it."
            )
            buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        else:
            self.note.setText("This file type cannot hold tags, so nothing can be edited.")
            self.add_button.hide()
            self.remove_button.hide()
            buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(info)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.note)
        layout.addLayout(edit_row)
        layout.addWidget(buttons)

    def _add_row(self, label: str, key: str, value: str, editable: bool) -> int:
        row = self.table.rowCount()
        self.table.insertRow(row)
        cells = (
            (FIELD_COL, label, False),
            (KEY_COL, key, False),
            (VALUE_COL, value, editable),
        )
        for column, text, can_edit in cells:
            item = QTableWidgetItem(text)
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if can_edit:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            if not editable:
                item.setForeground(self.palette().placeholderText())
            if column == VALUE_COL:
                item.setToolTip(text)
            self.table.setItem(row, column, item)
        if editable:
            self._editable_rows.add(row)
        return row

    def _update_remove_button(self):
        rows = {index.row() for index in self.table.selectedIndexes()}
        self.remove_button.setEnabled(any(row in self._editable_rows for row in rows))

    def add_field(self):
        hint = ADD_FIELD_HINTS.get(self._metadata.kind, "Field name")
        key, ok = QInputDialog.getText(self, "Add field", f"Field key\n{hint}:", QLineEdit.Normal)
        key = key.strip()
        if not ok or not key:
            return
        row = self._add_row(NEW_FIELD_LABEL, key, "", True)
        self.table.setCurrentCell(row, VALUE_COL)
        self.table.editItem(self.table.item(row, VALUE_COL))

    def remove_selected(self):
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            if row in self._editable_rows:
                # Hidden rather than deleted, so row numbers in _editable_rows stay valid.
                self.table.item(row, VALUE_COL).setText("")
                self.table.setRowHidden(row, True)
        self._update_remove_button()

    def edited_pairs(self):
        """(key, value) of every editable row as it is now; removed rows have no value."""
        return [
            (self.table.item(row, KEY_COL).text(), self.table.item(row, VALUE_COL).text())
            for row in sorted(self._editable_rows)
        ]

    def changes(self) -> Dict[str, List[str]]:
        return changed_fields(self._metadata.entries, self.edited_pairs())

    def accept(self):
        if self._metadata.can_add:
            # Commit a cell that is still being edited.
            self.table.setCurrentItem(None)
            changes = self.changes()
            if changes:
                try:
                    self._save(changes)
                except Exception as error:  # noqa: BLE001 - shown to the user, dialog stays open
                    QMessageBox.warning(self, "Could not save metadata", str(error))
                    return
        super().accept()
