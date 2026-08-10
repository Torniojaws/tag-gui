from typing import Dict, List, Sequence

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from .constants import DEFAULT_COLUMNS, STANDARD_TAG_FIELDS

MULTIPLE_VALUES = "(multiple values)"


class StandardTagsDialog(QDialog):
    """Edits standard tags of one or more tracks; fields left untouched are not written."""

    def __init__(self, track_fields: Sequence[List[str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit tags")
        self.setMinimumWidth(420)

        self._inputs: Dict[str, QLineEdit] = {}
        self._initial: Dict[str, str] = {}

        form = QFormLayout()
        for label, key in STANDARD_TAG_FIELDS:
            index = DEFAULT_COLUMNS.index(label)
            values = {fields[index].strip() for fields in track_fields}
            common = next(iter(values)) if len(values) == 1 else ""
            edit = QLineEdit(common)
            if len(values) > 1:
                edit.setPlaceholderText(MULTIPLE_VALUES)
            self._inputs[key] = edit
            self._initial[key] = common
            form.addRow(label, edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        count = len(track_fields)
        header = "Editing 1 file" if count == 1 else f"Editing {count} files"
        layout.addWidget(QLabel(header))
        layout.addLayout(form)
        layout.addWidget(buttons)

    def changed_values(self) -> Dict[str, str]:
        return {
            key: edit.text().strip()
            for key, edit in self._inputs.items()
            if edit.text().strip() != self._initial[key]
        }
