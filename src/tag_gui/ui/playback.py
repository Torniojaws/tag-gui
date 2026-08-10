"""The media player, its transport/volume/seek widgets and the playback commands."""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudio, QAudioOutput, QMediaPlayer

from ..constants import APP_TITLE, ARTIST_COLUMN, PATH_COLUMN, SONG_COLUMN
from ..core.utils import seconds_to_mmss
from .sliders import SeekSlider
from .styles import PAUSE_GLYPH, PLAY_GLYPH, PROGRESS_HEIGHT, PROGRESS_STYLE
from .table_fill import row_for_path, track_of
from .transport import TransportBar
from .volume import VolumeControls
from .window_base import WindowContext


class PlaybackMixin(WindowContext):
    def _build_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

    def _build_playback_widgets(self):
        self.transport = TransportBar()
        self.transport.previous_clicked.connect(self.play_previous)
        self.transport.play_pause_clicked.connect(self.toggle_play_pause)
        self.transport.stop_clicked.connect(self.player.stop)
        self.transport.next_clicked.connect(self.play_next)

        self.volume = VolumeControls()
        self.volume.volume_changed.connect(self.on_volume_changed)
        self.volume.mute_changed.connect(self.audio_output.setMuted)

        self.progress = SeekSlider(Qt.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(PROGRESS_HEIGHT)
        self.progress.setStyleSheet(PROGRESS_STYLE)
        self.progress.sliderMoved.connect(self.player.setPosition)

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
        table = self.current_table()
        if table.rowCount() == 0:
            return
        next_index = 0 if self.current_track_index < 0 else self.current_track_index + 1
        self.play_row(0 if next_index >= table.rowCount() else next_index)

    def play_previous(self):
        table = self.current_table()
        if table.rowCount() == 0:
            return
        last = table.rowCount() - 1
        self.play_row(last if self.current_track_index <= 0 else self.current_track_index - 1)

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
        if not self.progress.isSliderDown():
            self.progress.setValue(position)
        duration = self.player.duration() or 0
        self.progress.set_text(
            f"{seconds_to_mmss(position / 1000)} / {seconds_to_mmss(duration / 1000)}"
        )

    def on_duration_changed(self, duration: int):
        self.progress.setRange(0, max(0, duration))

    def on_volume_changed(self, value: int):
        # Sliders feel linear to the ear only after a logarithmic conversion.
        self.audio_output.setVolume(
            QAudio.convertVolume(value / 100, QAudio.LogarithmicVolumeScale, QAudio.LinearVolumeScale)
        )
