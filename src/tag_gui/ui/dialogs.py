from dataclasses import replace
from html import escape
from typing import Dict, List, Sequence

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..constants import DEFAULT_COLUMNS, STANDARD_TAG_FIELDS
from ..core.settings import SKIP_SECONDS_MAX, SKIP_SECONDS_MIN, Settings, parse_skip_seconds
from .styles import ERROR_COLOR

DIGITS = "0123456789"

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


class SkipSecondsInput(QLineEdit):
    """Keeps only digits, ignores out-of-range edits and falls back to the default when empty."""

    def __init__(self, value: int, parent=None):
        super().__init__(str(value), parent)
        self._value = value
        self.textEdited.connect(self._on_edited)

    def value(self) -> int:
        return self._value

    def _on_edited(self, text: str):
        cursor = self.cursorPosition()
        previous_text = str(self._value)
        self._value = parse_skip_seconds(text, self._value)
        new_text = str(self._value)
        if new_text == text:
            return
        self.setText(new_text)
        digits = "".join(ch for ch in text if ch in DIGITS)
        if not digits:
            # Selected, so typing straight away replaces the default instead of appending to it.
            self.selectAll()
            return
        if int(digits) == self._value:
            cursor = sum(ch in DIGITS for ch in text[:cursor])
        else:
            cursor -= len(text) - len(previous_text)
        self.setCursorPosition(max(0, min(cursor, len(new_text))))


class LastfmBox(QGroupBox):
    """Connect/disconnect scrobbling. Login happens on last.fm in the browser."""

    def __init__(self, lastfm=None, paused: bool = False, parent=None):
        super().__init__("Last.fm scrobbling", parent)
        self._lastfm = lastfm
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setOpenExternalLinks(True)
        self.pause_box = QCheckBox("Pause scrobbling")
        self.pause_box.setToolTip(
            "While checked, tracks are not scrobbled or tracked. Only tracks started after "
            "unchecking are scrobbled."
        )
        self.pause_box.setChecked(paused)
        self.connect_button = QPushButton("Connect to Last.fm...")
        self.disconnect_button = QPushButton("Disconnect")
        self.cancel_button = QPushButton("Cancel")
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {ERROR_COLOR};")
        self.error.hide()

        buttons = QHBoxLayout()
        for button in (self.connect_button, self.disconnect_button, self.cancel_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.error)
        layout.addLayout(buttons)
        layout.addWidget(self.pause_box)

        if lastfm is None or not lastfm.available:
            self.status.setText("Not available in this build (it has no Last.fm API key).")
            for button in (self.connect_button, self.disconnect_button, self.cancel_button):
                button.hide()
            self.pause_box.hide()
            return
        self.connect_button.clicked.connect(self._connect)
        self.disconnect_button.clicked.connect(lastfm.disconnect_account)
        self.cancel_button.clicked.connect(self._cancel)
        lastfm.account_changed.connect(self._show_account)
        lastfm.login_waiting.connect(self._show_waiting)
        lastfm.login_finished.connect(self._on_login_finished)
        self._show_account()

    def _connect(self):
        self.error.hide()
        self.status.setText("Contacting Last.fm...")
        self.connect_button.setEnabled(False)
        self._lastfm.connect_account()

    def _cancel(self):
        self._lastfm.cancel_login()
        self._show_account()

    def _show_waiting(self, url: str):
        self.status.setText(
            "Click <b>Yes, allow access</b> on the Last.fm page that opened in your browser. "
            f'<a href="{url}">Open the page again</a>'
        )
        self.connect_button.hide()
        self.disconnect_button.hide()
        self.cancel_button.show()

    def _on_login_finished(self, ok: bool, message: str):
        if not ok:
            self.error.setText(f"Could not connect: {message}")
            self.error.show()
        self._show_account()

    def _show_account(self):
        connected = self._lastfm.connected
        if connected:
            self.status.setText(f"Scrobbling as <b>{escape(self._lastfm.username)}</b>")
            self.error.hide()
        else:
            self.status.setText("Not connected. Plays are scrobbled once you connect.")
        self.connect_button.setEnabled(True)
        self.connect_button.setVisible(not connected)
        self.disconnect_button.setVisible(connected)
        self.cancel_button.hide()


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None, lastfm=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._original = settings

        self.skip_input = SkipSecondsInput(settings.skip_seconds)
        self.timebar_top = QCheckBox("Top")
        self.timebar_bottom = QCheckBox("Bottom")
        self.timebar_top.setChecked(settings.timebar_top)
        self.timebar_bottom.setChecked(settings.timebar_bottom)
        for box in (self.timebar_top, self.timebar_bottom):
            box.toggled.connect(self._keep_one_timebar)
        self._keep_one_timebar()

        timebar_row = QHBoxLayout()
        timebar_row.addWidget(self.timebar_top)
        timebar_row.addWidget(self.timebar_bottom)
        timebar_row.addStretch(1)

        form = QFormLayout()
        form.addRow(
            f"Left/Right skip in seconds ({SKIP_SECONDS_MIN}-{SKIP_SECONDS_MAX})", self.skip_input
        )
        form.addRow("Timebar position", timebar_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        self.lastfm_box = LastfmBox(lastfm, settings.scrobbling_paused)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.lastfm_box)
        layout.addWidget(buttons)

    def _keep_one_timebar(self):
        # The only checked box is locked, so the timebar can never be hidden entirely.
        self.timebar_top.setEnabled(self.timebar_bottom.isChecked())
        self.timebar_bottom.setEnabled(self.timebar_top.isChecked())

    def settings(self) -> Settings:
        # Fields edited elsewhere, like shuffle, pass through unchanged.
        return replace(
            self._original,
            skip_seconds=self.skip_input.value(),
            timebar_top=self.timebar_top.isChecked(),
            timebar_bottom=self.timebar_bottom.isChecked(),
            scrobbling_paused=self.lastfm_box.pause_box.isChecked(),
        )
