from pathlib import Path
from typing import List

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudio, QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..constants import (
    APP_TITLE,
    ARTIST_COLUMN,
    AUDIO_FILE_FILTER,
    DEFAULT_COLUMNS,
    PATH_COLUMN,
    PLAYLIST_FILE_FILTER,
    POPULATE_BATCH,
    PROGRESS_THRESHOLD,
    SONG_COLUMN,
)
from ..core.metadata import MetadataCache
from ..core.models import Playlist
from ..core.playlists import PlaylistStore
from ..core.scanning import collect_audio_files
from ..core.tags import parse_custom_tags, set_custom_tag, set_standard_tags
from ..core.utils import app_data_dir, seconds_to_mmss, slugify
from .dialogs import StandardTagsDialog
from .sizing import screen_geometry
from .sliders import SeekSlider
from .styles import ACTIONS_WIDTH_SHARE, PAUSE_GLYPH, PLAY_GLYPH, PROGRESS_HEIGHT, PROGRESS_STYLE
from .table import PlaylistTable
from .table_fill import (
    TAG_NAME_ROLE,
    fill_table,
    refresh_rows,
    row_for_path,
    selected_tracks,
    track_of,
)
from .tabs import PlaylistTabs
from .transport import TransportBar
from .volume import VolumeControls

ROW_MARGIN = 9
MAX_REPORTED_FAILURES = 10


class MainWindow(QMainWindow):
    def __init__(self, splash=None):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.data_dir = app_data_dir()
        self.custom_tags_file = self.data_dir / "custom_tags.txt"

        self.splash = splash
        self.custom_tags: List[str] = []
        self.store = PlaylistStore(self.data_dir)
        self.current_track_index = -1
        self._updating_table = False
        self.metadata = MetadataCache(self.data_dir / "metadata.json")
        self.metadata.load()

        self._build_player()
        self._build_tabs()
        self._build_layout()
        self.load_state()

    # ------------------------------------------------------------------ setup

    def _build_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

    def _build_tabs(self):
        self.tabs = PlaylistTabs()
        self.tabs.empty_double_clicked.connect(self.add_playlist)
        self.tabs.tabBarDoubleClicked.connect(self.on_tabbar_double_clicked)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabCloseRequested.connect(self.remove_playlist)
        tab_bar = self.tabs.tabBar()
        tab_bar.customContextMenuRequested.connect(self.on_tabbar_context_menu)
        tab_bar.tabMoved.connect(self.on_tab_moved)
        tab_bar.name_edited.connect(self.rename_playlist_to)
        tab_bar.middle_clicked.connect(self.remove_playlist)

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

    def _build_actions(self) -> QWidget:
        add_btn = QPushButton("Add Files")
        load_btn = QPushButton("Load Playlist")
        save_as_btn = QPushButton("Save As...")
        add_btn.clicked.connect(self.add_files_dialog)
        load_btn.clicked.connect(self.load_playlist_dialog)
        save_as_btn.clicked.connect(self.save_playlist_as)

        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        for button in (add_btn, load_btn, save_as_btn):
            layout.addWidget(button)
        geometry = screen_geometry()
        if geometry:
            actions.setMaximumWidth(round(geometry.width() * ACTIONS_WIDTH_SHARE))
        return actions

    def _build_controls_row(self) -> QHBoxLayout:
        self.transport = TransportBar()
        self.transport.previous_clicked.connect(self.play_previous)
        self.transport.play_pause_clicked.connect(self.toggle_play_pause)
        self.transport.stop_clicked.connect(self.player.stop)
        self.transport.next_clicked.connect(self.play_next)

        self.volume = VolumeControls()
        self.volume.volume_changed.connect(self.on_volume_changed)
        self.volume.mute_changed.connect(self.audio_output.setMuted)

        left = QHBoxLayout()
        left.addWidget(self.volume, 0, Qt.AlignVCenter)
        left.addStretch(1)

        right = QHBoxLayout()
        right.addStretch(1)
        right.addWidget(self._build_actions())

        # Equal stretch on both sides keeps the transport centered in the window, not just
        # in the space left over by the action buttons.
        row = QHBoxLayout()
        row.setContentsMargins(ROW_MARGIN, 0, ROW_MARGIN, 6)
        row.addLayout(left, 1)
        row.addWidget(self.transport)
        row.addLayout(right, 1)
        return row

    def _build_layout(self):
        self.progress = SeekSlider(Qt.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(PROGRESS_HEIGHT)
        self.progress.setStyleSheet(PROGRESS_STYLE)
        self.progress.sliderMoved.connect(self.player.setPosition)

        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(ROW_MARGIN, 0, ROW_MARGIN, 0)
        tabs_row.addWidget(self.tabs)

        central = QWidget()
        layout = QVBoxLayout(central)
        # Only the seek bar reaches the window edges, so the margins live on the other rows.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._build_tags_row())
        layout.addLayout(tabs_row)
        layout.addLayout(self._build_controls_row())
        layout.addWidget(self.progress)
        self.setCentralWidget(central)

    # ------------------------------------------------------------- accessors

    @property
    def playlists(self) -> List[Playlist]:
        return self.store.playlists

    def current_playlist(self) -> Playlist:
        return self.playlists[self.tabs.currentIndex()]

    def current_table(self) -> PlaylistTable:
        return self.tabs.currentWidget()

    def create_table(self) -> PlaylistTable:
        table = PlaylistTable(self.add_tracks_to_current_playlist, self.remove_selected_tracks)
        table.customContextMenuRequested.connect(self.on_table_context_menu)
        table.itemDoubleClicked.connect(self.on_item_double_clicked)
        table.itemChanged.connect(self.on_item_changed)
        return table

    # -------------------------------------------------------------- playlists

    def on_tabbar_double_clicked(self, index):
        if index != -1:
            self.tabs.tabBar().edit_tab(index)

    def on_tabbar_context_menu(self, pos):
        tab_bar = self.tabs.tabBar()
        index = tab_bar.tabAt(pos)
        menu = QMenu(self)
        add_action = menu.addAction("Add playlist")
        load_action = menu.addAction("Load playlist...")
        remove_action = menu.addAction("Remove playlist") if index != -1 else None
        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen is add_action:
            self.add_playlist()
        elif chosen is load_action:
            self.load_playlist_dialog()
        elif chosen is not None and chosen is remove_action:
            self.remove_playlist(index)

    def add_playlist(self):
        self.open_playlist(self.store.next_default())

    def open_playlist(self, playlist: Playlist):
        self.playlists.append(playlist)
        table = self.create_table()
        self.tabs.addTab(table, playlist.name)
        self.populate_table(table, playlist)
        self.tabs.setCurrentWidget(table)
        self.save_state()

    def load_playlist_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Playlist", str(self.data_dir), PLAYLIST_FILE_FILTER
        )
        if not path:
            return
        chosen = Path(path)
        for index, playlist in enumerate(self.playlists):
            if self.store.path_for(playlist) == chosen:
                self.tabs.setCurrentIndex(index)
                return
        name, tracks = self.store.read_m3u(chosen)
        self.open_playlist(Playlist(name=name or chosen.stem, file_name=str(chosen), tracks=tracks))

    def remove_playlist(self, index: int):
        if not 0 <= index < len(self.playlists):
            return
        playlist = self.playlists[index]
        answer = QMessageBox.question(
            self,
            "Remove playlist",
            f"Remove playlist '{playlist.name}' from the list?\n"
            f"{self.store.path_for(playlist)} is kept on disk and can be loaded again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        del self.playlists[index]
        self.current_track_index = -1
        if self.playlists:
            self.save_state()
        else:
            self.add_playlist()

    def rename_playlist_to(self, index: int, new_name: str):
        if not 0 <= index < len(self.playlists):
            return
        if self.store.rename(index, new_name):
            self.tabs.setTabText(index, self.playlists[index].name)
            self.save_state()

    def save_playlist_as(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return
        playlist = self.playlists[index]
        suggested = self.store.path_for(playlist).with_name(f"{slugify(playlist.name)}.m3u")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist As", str(suggested), PLAYLIST_FILE_FILTER
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() not in (".m3u", ".m3u8"):
            target = target.with_suffix(".m3u")
        # The previous file is left alone; the playlist simply continues in its new location.
        playlist.file_name = str(target)
        self.save_state()

    def on_tab_changed(self, _index):
        self.current_track_index = -1

    def on_tab_moved(self, from_index: int, to_index: int):
        self.store.move(from_index, to_index)
        self.save_state()

    # ------------------------------------------------------------------ state

    def load_custom_tags(self):
        if self.custom_tags_file.exists():
            self.custom_tags = parse_custom_tags(self.custom_tags_file.read_text(encoding="utf-8"))
        else:
            self.custom_tags = []
        self.tags_input.setText(", ".join(self.custom_tags))

    def save_custom_tags(self):
        self.custom_tags_file.write_text(",".join(self.custom_tags), encoding="utf-8")

    def load_state(self):
        self.load_custom_tags()
        active_index = self.store.load()
        for playlist in self.playlists:
            table = self.create_table()
            self.tabs.addTab(table, playlist.name)
            self.populate_table(table, playlist)
        self.tabs.setCurrentIndex(min(active_index, self.tabs.count() - 1))
        self.splash = None
        self.save_state()

    def save_state(self):
        self.store.save(self.tabs.currentIndex())
        self.metadata.save(keep=self.store.all_tracks())

    def apply_custom_tags(self):
        self.custom_tags = parse_custom_tags(self.tags_input.text())
        self.save_custom_tags()
        for index, playlist in enumerate(self.playlists):
            self.populate_table(self.tabs.widget(index), playlist)
        self.save_state()

    # ------------------------------------------------------------------ table

    def populate_table(self, table: PlaylistTable, playlist: Playlist):
        update, finish = self.start_progress(
            f"Reading tags for {playlist.name}", len(playlist.tracks)
        )
        self._updating_table = True
        try:
            fill_table(table, playlist, self.custom_tags, self.metadata, update)
        finally:
            finish()
            self._updating_table = False

    def refresh_tracks(self, table: PlaylistTable, tracks: List[str]):
        self._updating_table = True
        try:
            refresh_rows(table, tracks, self.custom_tags, self.metadata)
        finally:
            self._updating_table = False

    def start_progress(self, label: str, total: int):
        """Report progress on the splash while starting, in a modal dialog afterwards."""
        if self.splash is not None:
            self.splash.begin(label, total)
            return self.splash.update_progress, self.splash.end
        if total <= PROGRESS_THRESHOLD:
            return (lambda _value: None), (lambda: None)
        dialog = QProgressDialog(f"{label}...", None, 0, total, self)
        dialog.setWindowTitle("Loading playlist")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setMinimumDuration(300)

        def update(value: int):
            dialog.setValue(value)
            QApplication.processEvents()

        return update, dialog.close

    # ------------------------------------------------------------------ files

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", AUDIO_FILE_FILTER)
        if paths:
            self.add_tracks_to_current_playlist([str(Path(p)) for p in paths])

    def add_tracks_to_current_playlist(self, paths: List[str]):
        tracks = self.scan_for_audio_files(paths)
        if not tracks:
            return
        playlist = self.current_playlist()
        known = set(playlist.tracks)
        for track in tracks:
            if track not in known:
                known.add(track)
                playlist.tracks.append(track)
        self.populate_table(self.current_table(), playlist)
        self.save_state()

    def scan_for_audio_files(self, paths: List[str]) -> List[str]:
        """Expand dropped folders into audio files, reporting progress for big trees."""
        progress = QProgressDialog("Scanning for audio files...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Add files")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(300)

        def on_progress(count: int):
            if count % POPULATE_BATCH:
                return
            progress.setLabelText(f"Scanning for audio files... {count} found")
            QApplication.processEvents()

        try:
            return collect_audio_files(paths, on_progress, progress.wasCanceled)
        finally:
            progress.close()

    def remove_selected_tracks(self):
        table = self.current_table()
        paths = selected_tracks(table)
        if not paths:
            return
        if len(paths) > 1:
            answer = QMessageBox.question(
                self,
                "Remove files",
                f"Remove {len(paths)} files from the playlist?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        removed = {Path(p) for p in paths}
        playing = self.player.source().toLocalFile()
        playlist = self.current_playlist()
        playlist.tracks = [t for t in playlist.tracks if Path(t) not in removed]
        for track in paths:
            self.metadata.discard(track)
        self.populate_table(table, playlist)

        if playing and Path(playing) in removed:
            self.player.stop()
            self.player.setSource(QUrl())
            self.current_track_index = -1
        else:
            self.current_track_index = row_for_path(table, playing)
        self.save_state()

    # ------------------------------------------------------------------- tags

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

    # --------------------------------------------------------------- playback

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

    def closeEvent(self, event):
        self.save_custom_tags()
        self.save_state()
        self.metadata.save()
        super().closeEvent(event)
