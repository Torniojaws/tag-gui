import json
from pathlib import Path
from typing import List

from PySide6.QtCore import QUrl, Qt
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    ACTIONS_WIDTH_SHARE,
    APP_TITLE,
    ARTIST_COLUMN,
    AUDIO_FILE_FILTER,
    DEFAULT_COLUMNS,
    DURATION_COLUMN,
    DURATION_COLUMN_PADDING,
    NEXT_BUTTON_GLYPH,
    PAUSE_BUTTON_GLYPH,
    PAUSE_BUTTON_STYLE,
    PAUSE_GLYPH,
    PLAY_BUTTON_GLYPH,
    PLAY_BUTTON_STYLE,
    PLAY_GLYPH,
    POPULATE_BATCH,
    PREV_BUTTON_GLYPH,
    PROGRESS_THRESHOLD,
    SELECTION_STYLE,
    SONG_COLUMN,
    STOP_BUTTON_GLYPH,
    STOP_BUTTON_STYLE,
    TRANSPORT_BUTTON_RANGE,
    TRANSPORT_BUTTON_SCALE,
    YEAR_COLUMN,
)
from .models import Playlist
from .metadata import MetadataCache
from .dialogs import StandardTagsDialog
from .tags import parse_custom_tags, set_custom_tag, set_standard_tags
from .utils import app_data_dir, collect_audio_files, seconds_to_mmss
from .widgets import CenteredCheckDelegate, PlaylistTable, SeekSlider, TagCheckItem


def screen_size():
    screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def transport_button_size() -> int:
    geometry = screen_size()
    height = geometry.height() if geometry else 900
    smallest, largest = TRANSPORT_BUTTON_RANGE
    return max(smallest, min(largest, round(height * TRANSPORT_BUTTON_SCALE)))


class MainWindow(QMainWindow):
    def __init__(self, splash=None):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.data_dir = app_data_dir()
        self.custom_tags_file = self.data_dir / "custom_tags.txt"
        self.playlists_file = self.data_dir / "playlists.json"

        self.splash = splash
        self.custom_tags: List[str] = []
        self.playlists: List[Playlist] = []
        self.current_track_index = -1
        self._updating_table = False
        self.metadata = MetadataCache(self.data_dir / "metadata.json")
        self.metadata.load()

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.tabBarDoubleClicked.connect(self.on_tabbar_double_clicked)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabBar().setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self.on_tabbar_context_menu)
        self.tabs.tabBar().tabMoved.connect(self.on_tab_moved)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Custom checkbox tags (comma separated)")
        apply_tags_button = QPushButton("Apply Tags")
        apply_tags_button.clicked.connect(self.apply_custom_tags)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton(PREV_BUTTON_GLYPH)
        self.play_btn = QPushButton(PLAY_BUTTON_GLYPH)
        self.stop_btn = QPushButton(STOP_BUTTON_GLYPH)
        self.next_btn = QPushButton(NEXT_BUTTON_GLYPH)
        self.add_btn = QPushButton("Add Files")
        self.add_playlist_btn = QPushButton("Add Playlist")
        self.rename_btn = QPushButton("Rename / Save As")

        self.prev_btn.clicked.connect(self.play_previous)
        self.play_btn.clicked.connect(self.toggle_play_pause)
        self.stop_btn.clicked.connect(self.player.stop)
        self.next_btn.clicked.connect(self.play_next)
        self.add_btn.clicked.connect(self.add_files_dialog)
        self.add_playlist_btn.clicked.connect(self.add_playlist)
        self.rename_btn.clicked.connect(self.rename_playlist)

        transport = QHBoxLayout()
        transport.setSpacing(8)
        button_size = transport_button_size()
        for btn, tip in (
            (self.prev_btn, "Previous"),
            (self.play_btn, "Play"),
            (self.stop_btn, "Stop"),
            (self.next_btn, "Next"),
        ):
            btn.setToolTip(tip)
            btn.setFixedSize(button_size, button_size)
            glyph_font = btn.font()
            glyph_font.setPixelSize(round(button_size * 0.4))
            btn.setFont(glyph_font)
            transport.addWidget(btn)
        self.play_btn.setStyleSheet(PLAY_BUTTON_STYLE)
        self.stop_btn.setStyleSheet(STOP_BUTTON_STYLE)

        actions = QWidget()
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        for btn in (self.add_btn, self.add_playlist_btn, self.rename_btn):
            actions_layout.addWidget(btn)
        geometry = screen_size()
        if geometry:
            actions.setMaximumWidth(round(geometry.width() * ACTIONS_WIDTH_SHARE))

        controls.addLayout(transport)
        controls.addStretch(1)
        controls.addWidget(actions)

        self.progress = SeekSlider(Qt.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.sliderMoved.connect(self.player.setPosition)
        self.progress_label = QLabel("00:00 / 00:00")

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.progress_label)

        tags_layout = QHBoxLayout()
        tags_layout.addWidget(self.tags_input)
        tags_layout.addWidget(apply_tags_button)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(tags_layout)
        layout.addWidget(self.tabs)
        layout.addLayout(controls)
        layout.addLayout(progress_layout)
        self.setCentralWidget(central)

        self.load_state()

    def current_playlist(self) -> Playlist:
        return self.playlists[self.tabs.currentIndex()]

    def current_table(self) -> PlaylistTable:
        return self.tabs.currentWidget()

    def create_table(self):
        table = PlaylistTable(self.add_tracks_to_current_playlist, self.remove_selected_tracks)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setStyleSheet(SELECTION_STYLE)
        table.horizontalHeader().setSectionsMovable(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        # Sizing columns against every row is too slow for large playlists.
        table.horizontalHeader().setResizeContentsPrecision(50)
        table.verticalHeader().setVisible(False)
        table.setItemDelegate(CenteredCheckDelegate(table))
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self.on_table_context_menu)
        table.itemDoubleClicked.connect(self.on_item_double_clicked)
        table.itemChanged.connect(self.on_item_changed)
        return table

    def on_tabbar_double_clicked(self, index):
        if index != -1:
            return
        self.add_playlist()

    def on_tabbar_context_menu(self, pos):
        tab_bar = self.tabs.tabBar()
        index = tab_bar.tabAt(pos)
        menu = QMenu(self)
        add_action = menu.addAction("Add playlist")
        remove_action = menu.addAction("Remove playlist") if index != -1 else None
        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen is add_action:
            self.add_playlist()
        elif chosen is not None and chosen is remove_action:
            self.remove_playlist(index)

    def add_playlist(self):
        name, file_name = self.next_default_playlist_name()
        playlist = Playlist(name=name, file_name=file_name, tracks=[])
        self.playlists.append(playlist)
        table = self.create_table()
        self.tabs.addTab(table, playlist.name)
        self.populate_table(table, playlist)
        self.tabs.setCurrentWidget(table)
        self.save_state()

    def remove_playlist(self, index: int):
        if not 0 <= index < len(self.playlists):
            return
        playlist = self.playlists[index]
        answer = QMessageBox.question(
            self,
            "Remove playlist",
            f"Remove playlist '{playlist.name}'?\nThis also deletes {playlist.file_name}.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        del self.playlists[index]
        m3u_path = self.data_dir / playlist.file_name
        if m3u_path.exists():
            m3u_path.unlink()
        self.current_track_index = -1
        if self.playlists:
            self.save_state()
        else:
            self.add_playlist()

    def on_tab_changed(self, _index):
        self.current_track_index = -1

    def on_tab_moved(self, from_index: int, to_index: int):
        self.playlists.insert(to_index, self.playlists.pop(from_index))
        self.save_state()

    def next_default_playlist_name(self):
        used = {p.file_name.lower() for p in self.playlists}
        if "default.m3u" not in used:
            return "default", "default.m3u"
        i = 1
        while True:
            candidate = f"default{i}.m3u"
            if candidate.lower() not in used:
                return f"default{i}", candidate
            i += 1

    def load_custom_tags(self):
        if self.custom_tags_file.exists():
            text = self.custom_tags_file.read_text(encoding="utf-8")
            self.custom_tags = parse_custom_tags(text)
        else:
            self.custom_tags = []
        self.tags_input.setText(", ".join(self.custom_tags))

    def save_custom_tags(self):
        self.custom_tags_file.write_text(",".join(self.custom_tags), encoding="utf-8")

    def load_m3u_tracks(self, file_name: str) -> List[str]:
        m3u_path = self.data_dir / file_name
        tracks = []
        if not m3u_path.exists():
            return tracks
        for line in m3u_path.read_text(encoding="utf-8").splitlines():
            path = line.strip()
            if not path or path.startswith("#"):
                continue
            tracks.append(path)
        return tracks

    def save_playlist_file(self, playlist: Playlist):
        m3u_path = self.data_dir / playlist.file_name
        lines = ["#EXTM3U"] + playlist.tracks
        m3u_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load_state(self):
        self.load_custom_tags()

        if self.playlists_file.exists():
            state = json.loads(self.playlists_file.read_text(encoding="utf-8"))
            self.playlists = [
                Playlist(name=p["name"], file_name=p["file_name"], tracks=self.load_m3u_tracks(p["file_name"]))
                for p in state.get("playlists", [])
            ]
            active_index = int(state.get("active_index", 0))
        else:
            self.playlists = []
            active_index = 0

        if not self.playlists:
            self.playlists = [Playlist(name="default", file_name="default.m3u", tracks=[])]

        for playlist in self.playlists:
            table = self.create_table()
            self.tabs.addTab(table, playlist.name)
            self.populate_table(table, playlist)

        self.tabs.setCurrentIndex(min(active_index, self.tabs.count() - 1))
        self.splash = None
        self.save_state()

    def save_state(self):
        for playlist in self.playlists:
            self.save_playlist_file(playlist)
        state = {
            "active_index": self.tabs.currentIndex(),
            "playlists": [{"name": p.name, "file_name": p.file_name} for p in self.playlists],
        }
        self.playlists_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        self.metadata.save(keep={track for p in self.playlists for track in p.tracks})

    def apply_custom_tags(self):
        self.custom_tags = parse_custom_tags(self.tags_input.text())
        self.save_custom_tags()
        for idx, playlist in enumerate(self.playlists):
            table = self.tabs.widget(idx)
            self.populate_table(table, playlist)
        self.save_state()

    def populate_table(self, table: PlaylistTable, playlist: Playlist):
        self._updating_table = True
        update, finish = self.start_progress(f"Reading tags for {playlist.name}", len(playlist.tracks))
        try:
            headers = DEFAULT_COLUMNS + self.custom_tags
            table.clear()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(playlist.tracks))

            for row, track in enumerate(playlist.tracks):
                if row % POPULATE_BATCH == 0:
                    update(row)
                info = self.metadata.get(track, self.custom_tags)
                for col, value in enumerate(info.fields):
                    item = QTableWidgetItem(value)
                    # Standard tags are edited through the right-click dialog, never inline.
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if col == YEAR_COLUMN:
                        item.setTextAlignment(Qt.AlignCenter)
                    elif col == DURATION_COLUMN:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if col == 0:
                        item.setData(Qt.UserRole, track)
                    table.setItem(row, col, item)

                for offset, tag in enumerate(self.custom_tags):
                    col = len(DEFAULT_COLUMNS) + offset
                    item = TagCheckItem()
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setCheckState(Qt.Checked if info.tag_states.get(tag) else Qt.Unchecked)
                    item.setData(Qt.UserRole, track)
                    item.setData(Qt.UserRole + 1, tag)
                    table.setItem(row, col, item)
            table.reapply_sort()
            table.apply_album_colors()
            table.resizeColumnsToContents()
            width = table.fontMetrics().horizontalAdvance("00:00") + DURATION_COLUMN_PADDING
            table.setColumnWidth(DURATION_COLUMN, width)
        finally:
            finish()
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
        table = self.current_table()
        self.populate_table(table, playlist)
        self.save_state()

    def on_table_context_menu(self, pos):
        table = self.current_table()
        tracks = self.selected_tracks(table)
        menu = QMenu(self)
        edit_action = menu.addAction("Edit tags...")
        edit_action.setEnabled(bool(tracks))
        if menu.exec(table.mapToGlobal(pos)) is edit_action:
            self.edit_selected_tags()

    def selected_tracks(self, table: PlaylistTable) -> List[str]:
        tracks = []
        seen = set()
        for row in sorted({index.row() for index in table.selectedIndexes()}):
            item = table.item(row, 0)
            track = item.data(Qt.UserRole) if item else None
            if track and track not in seen:
                seen.add(track)
                tracks.append(track)
        return tracks

    def edit_selected_tags(self):
        table = self.current_table()
        tracks = self.selected_tracks(table)
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
        for track in tracks:
            try:
                set_standard_tags(Path(track), values)
            except Exception as exc:
                failures.append(f"{Path(track).name}: {exc}")
            else:
                self.metadata.discard(track)
        self.populate_table(table, self.current_playlist())
        if failures:
            shown = "\n".join(failures[:10])
            more = "" if len(failures) <= 10 else f"\n...and {len(failures) - 10} more"
            QMessageBox.warning(self, "Tag write failed", f"Could not update:\n{shown}{more}")

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

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            "",
            AUDIO_FILE_FILTER,
        )
        if paths:
            self.add_tracks_to_current_playlist([str(Path(p)) for p in paths])

    def row_for_path(self, table: PlaylistTable, path: str) -> int:
        if not path:
            return -1
        target = Path(path)
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            stored = item.data(Qt.UserRole) if item else None
            if stored and Path(stored) == target:
                return row
        return -1

    def remove_selected_tracks(self):
        table = self.current_table()
        rows = sorted({index.row() for index in table.selectedIndexes()})
        paths = []
        for row in rows:
            item = table.item(row, 0)
            stored = item.data(Qt.UserRole) if item else None
            if stored:
                paths.append(stored)
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
            self.current_track_index = self.row_for_path(table, playing)
        self.save_state()

    def on_item_double_clicked(self, item):
        self.play_row(item.row())

    def on_item_changed(self, item):
        if self._updating_table:
            return
        col = item.column()
        if col < len(DEFAULT_COLUMNS):
            return

        track = item.data(Qt.UserRole)
        tag = item.data(Qt.UserRole + 1)
        if not track or not tag:
            return

        checked = item.checkState() == Qt.Checked
        try:
            set_custom_tag(Path(track), tag, checked)
        except Exception as exc:
            QMessageBox.warning(self, "Tag write failed", f"Could not update tag '{tag}' for file:\n{track}\n\n{exc}")
            self._updating_table = True
            try:
                item.setCheckState(Qt.Unchecked if checked else Qt.Checked)
            finally:
                self._updating_table = False
            return
        self.metadata.update_tag_state(track, tag, checked)

    def play_row(self, row: int):
        table = self.current_table()
        if row < 0 or row >= table.rowCount():
            return
        path_item = table.item(row, 0)
        if not path_item:
            return
        file_path = path_item.data(Qt.UserRole)
        if not file_path:
            return
        self.current_track_index = row
        self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.play()
        table.selectRow(row)

    def playing_title(self, file_path: str) -> str:
        info = self.metadata.get(file_path, self.custom_tags)
        artist, song = info.fields[ARTIST_COLUMN], info.fields[SONG_COLUMN]
        if song == Path(file_path).stem:
            # track_fields falls back to the stem, so the file carries no title tag.
            song = Path(file_path).name
        return f"{artist} - {song}" if artist else song

    def on_playback_state_changed(self, state):
        playing = state == QMediaPlayer.PlayingState
        self.play_btn.setText(PAUSE_BUTTON_GLYPH if playing else PLAY_BUTTON_GLYPH)
        self.play_btn.setToolTip("Pause" if playing else "Play")
        self.play_btn.setStyleSheet(PAUSE_BUTTON_STYLE if playing else PLAY_BUTTON_STYLE)
        source = self.player.source().toLocalFile()
        if not source:
            self.setWindowTitle(APP_TITLE)
            return
        if state == QMediaPlayer.PlayingState:
            self.setWindowTitle(f"{APP_TITLE} - {PLAY_GLYPH} Playing: {self.playing_title(source)}")
        elif state == QMediaPlayer.PausedState:
            self.setWindowTitle(f"{APP_TITLE} - {PAUSE_GLYPH} Paused: {self.playing_title(source)}")
        else:
            self.setWindowTitle(APP_TITLE)

    def toggle_play_pause(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlayingState:
            self.player.pause()
            return
        table = self.current_table()
        selected = table.currentRow()
        if state == QMediaPlayer.PausedState:
            paused_row = self.row_for_path(table, self.player.source().toLocalFile())
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
        if next_index >= table.rowCount():
            next_index = 0
        self.play_row(next_index)

    def play_previous(self):
        table = self.current_table()
        if table.rowCount() == 0:
            return
        prev_index = table.rowCount() - 1 if self.current_track_index <= 0 else self.current_track_index - 1
        self.play_row(prev_index)

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.play_next()

    def on_position_changed(self, position: int):
        if not self.progress.isSliderDown():
            self.progress.setValue(position)
        duration = self.player.duration() or 0
        self.progress_label.setText(f"{seconds_to_mmss(position / 1000)} / {seconds_to_mmss(duration / 1000)}")

    def on_duration_changed(self, duration: int):
        self.progress.setRange(0, max(0, duration))

    def rename_playlist(self):
        idx = self.tabs.currentIndex()
        if idx < 0:
            return
        playlist = self.playlists[idx]
        old_file_name = playlist.file_name
        new_name, ok = QInputDialog.getText(self, "Rename playlist", "Playlist name:", text=playlist.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            return

        new_file, ok2 = QInputDialog.getText(self, "Save as", "Playlist filename (.m3u):", text=playlist.file_name)
        if not ok2:
            return
        new_file = new_file.strip()
        if not new_file:
            return
        if not new_file.lower().endswith(".m3u"):
            new_file += ".m3u"
        if Path(new_file).name != new_file:
            QMessageBox.warning(self, "Invalid filename", "Playlist filename must not include directories.")
            return
        if any(i != idx and p.file_name.lower() == new_file.lower() for i, p in enumerate(self.playlists)):
            QMessageBox.warning(self, "Filename in use", "Another playlist is already using that .m3u filename.")
            return

        playlist.name = new_name
        playlist.file_name = new_file
        self.tabs.setTabText(idx, new_name)
        self.save_state()
        if old_file_name.lower() != new_file.lower():
            old_path = self.data_dir / old_file_name
            if old_path.exists():
                old_path.unlink()

    def closeEvent(self, event):
        self.save_custom_tags()
        self.save_state()
        self.metadata.save()
        super().closeEvent(event)
