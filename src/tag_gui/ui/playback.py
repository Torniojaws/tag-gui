"""The media player, its transport/volume/seek widgets and the playback commands."""

from pathlib import Path
from typing import Tuple

from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtMultimedia import QAudio, QAudioOutput, QMediaDevices, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
)

from ..constants import APP_TITLE, ARTIST_COLUMN, PATH_COLUMN, SONG_COLUMN
from ..core.utils import seconds_to_mmss
from .sliders import SeekSlider
from .styles import PAUSE_GLYPH, PLAY_GLYPH, PROGRESS_HEIGHT, PROGRESS_STYLE
from .table_fill import row_for_path, track_of
from .transport import TransportBar
from .volume import VolumeControls
from .window_base import WindowContext

# Left/Right keep moving the text cursor while one of these has focus.
TEXT_INPUTS = (QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit)


class PlaybackMixin(WindowContext):
    def _build_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput(QMediaDevices.defaultAudioOutput())
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)
        self._skip_blocked = False
        # Application-wide, so the arrows skip before the table or tab bar can claim them.
        QApplication.instance().installEventFilter(self)

    def _build_playback_widgets(self):
        self.transport = TransportBar()
        self.transport.previous_clicked.connect(self.play_previous)
        self.transport.play_pause_clicked.connect(self.toggle_play_pause)
        self.transport.stop_clicked.connect(self.player.stop)
        self.transport.next_clicked.connect(self.play_next)

        self.volume = VolumeControls()
        self.volume.volume_changed.connect(self.on_volume_changed)
        self.volume.mute_changed.connect(self.audio_output.setMuted)

        self.progress_top = self._build_seek_bar()
        self.progress_bottom = self._build_seek_bar()

    def _build_seek_bar(self) -> SeekSlider:
        bar = SeekSlider(Qt.Horizontal)
        bar.setRange(0, 0)
        bar.setFixedHeight(PROGRESS_HEIGHT)
        bar.setStyleSheet(PROGRESS_STYLE)
        bar.sliderMoved.connect(self.player.setPosition)
        return bar

    def seek_bars(self) -> Tuple[SeekSlider, SeekSlider]:
        return self.progress_top, self.progress_bottom

    def eventFilter(self, watched, event):
        if event.type() == QEvent.KeyPress and self._handle_skip_key(event):
            return True
        return super().eventFilter(watched, event)

    def _handle_skip_key(self, event) -> bool:
        if event.key() == Qt.Key_Left:
            direction = -1
        elif event.key() == Qt.Key_Right:
            direction = 1
        else:
            return False
        if event.modifiers() not in (Qt.NoModifier, Qt.KeypadModifier):
            return False
        if not self.isActiveWindow() or isinstance(QApplication.focusWidget(), TEXT_INPUTS):
            return False
        # A held key stops at the song boundary; only a fresh press skips on from there.
        if event.isAutoRepeat() and self._skip_blocked:
            return True
        if self.player.playbackState() != QMediaPlayer.PlayingState:
            return False
        self._skip_blocked = self.skip(direction)
        return True

    def skip(self, direction: int) -> bool:
        """Seek by the configured step; returns True when the start or end of the song is hit."""
        target = self.player.position() + direction * self.settings.skip_seconds * 1000
        if target <= 0:
            self.player.setPosition(0)
            return True
        duration = self.player.duration()
        if 0 < duration <= target:
            self.play_next()
            return True
        self.player.setPosition(target)
        return False

    def on_item_double_clicked(self, item):
        self.play_row(item.row())

    def play_row(self, row: int):
        table = self.current_table()
        if row < 0 or row >= table.rowCount():
            return
        file_path = track_of(table.item(row, PATH_COLUMN))
        if not file_path:
            return
        self.current_track_index = row
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        table.selectRow(row)

    def toggle_play_pause(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlayingState:
            self.player.pause()
            return
        table = self.current_table()
        selected = table.currentRow()
        if state == QMediaPlayer.PausedState:
            paused_row = row_for_path(table, self.player.source().toLocalFile())
            if selected < 0 or selected == paused_row:
                self.player.play()
                return
        if selected >= 0:
            self.play_row(selected)

    def play_next(self):
        self._play_step(1)

    def play_previous(self):
        self._play_step(-1)

    def _play_step(self, direction: int):
        """Play the next/previous row that the filter leaves visible, wrapping around."""
        table = self.current_table()
        rows = table.rowCount()
        if rows == 0:
            return
        current = self.current_track_index
        # From no track (or the first one), previous wraps to the last row.
        start = max(current, 0) if direction < 0 else current
        for step in range(1, rows + 1):
            row = (start + direction * step) % rows
            if not table.isRowHidden(row):
                self.play_row(row)
                return

    def playing_title(self, file_path: str) -> str:
        info = self.metadata.get(file_path, self.custom_tags)
        artist, song = info.fields[ARTIST_COLUMN], info.fields[SONG_COLUMN]
        if song == Path(file_path).stem:
            # track_fields falls back to the stem, so the file carries no title tag.
            song = Path(file_path).name
        return f"{artist} - {song}" if artist else song

    def on_playback_state_changed(self, state):
        self.transport.set_playing(state == QMediaPlayer.PlayingState)
        source = self.player.source().toLocalFile()
        if not source:
            self.setWindowTitle(APP_TITLE)
        elif state == QMediaPlayer.PlayingState:
            self.setWindowTitle(f"{APP_TITLE} - {PLAY_GLYPH} Playing: {self.playing_title(source)}")
        elif state == QMediaPlayer.PausedState:
            self.setWindowTitle(f"{APP_TITLE} - {PAUSE_GLYPH} Paused: {self.playing_title(source)}")
        else:
            self.setWindowTitle(APP_TITLE)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.play_next()

    def on_position_changed(self, position: int):
        duration = self.player.duration() or 0
        text = f"{seconds_to_mmss(position / 1000)} / {seconds_to_mmss(duration / 1000)}"
        for bar in self.seek_bars():
            if not bar.isSliderDown():
                bar.setValue(position)
            bar.set_text(text)

    def on_duration_changed(self, duration: int):
        for bar in self.seek_bars():
            bar.setRange(0, max(0, duration))

    def on_volume_changed(self, value: int):
        # Sliders feel linear to the ear only after a logarithmic conversion.
        self.audio_output.setVolume(
            QAudio.convertVolume(value / 100, QAudio.LogarithmicVolumeScale, QAudio.LinearVolumeScale)
        )
