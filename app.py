import json
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

AUDIO_EXTENSIONS = {".mp3", ".flac"}
DEFAULT_COLUMNS = ["Artist", "Song", "Album", "Year", "Duration"]
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_ID = "tag-gui.tag-gui"
# Explicit background/text pair so selected rows stay readable under light and dark themes.
SELECTION_STYLE = """
QTableView { selection-background-color: #5a67a3; selection-color: #ffffff; }
QTableView::item:selected { background: #5a67a3; color: #ffffff; }
QTableView::item:selected:!active { background: #5a67a3; color: #ffffff; }
"""


def note_pixmap(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.TextAntialiasing)
    font = QFont("Segoe UI Symbol")
    font.setPixelSize(int(size * 0.9))
    painter.setFont(font)
    painter.setPen(QColor("#2d6cdf"))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "\u266a")
    painter.end()
    return pixmap


def note_icon() -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(note_pixmap(size))
    return icon


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    path = base / "tag-gui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def seconds_to_mmss(seconds: float) -> str:
    total = int(seconds or 0)
    return f"{total // 60:02d}:{total % 60:02d}"


def parse_custom_tags(text: str) -> List[str]:
    tags = []
    seen = set()
    for part in text.split(","):
        t = unicodedata.normalize("NFC", part.strip())
        key = normalize_tag_name(t)
        if t and key not in seen:
            seen.add(key)
            tags.append(t)
    return tags


def ascii_tag_key(name: str) -> str:
    """Tag names are shown as typed but stored as ASCII, so "Yömusa" is written as "Yomusa"."""
    key = []
    for char in unicodedata.normalize("NFKD", str(name).strip()):
        if unicodedata.combining(char):
            continue
        key.append(char if " " <= char <= "}" and char != "=" else "_")
    return "".join(key)


def normalize_tag_name(name: str) -> str:
    return ascii_tag_key(name).casefold()


def load_easy_tags(path: Path):
    try:
        return MutagenFile(str(path), easy=True)
    except Exception:
        return None


def load_raw_tags(path: Path):
    try:
        return MutagenFile(str(path), easy=False)
    except Exception:
        return None


def get_field(tags, key: str) -> str:
    if not tags:
        return ""
    values = tags.get(key)
    if not values:
        return ""
    value = values[0]
    return str(value)


def get_duration(path: Path) -> str:
    audio = load_raw_tags(path)
    if audio is None or not getattr(audio, "info", None):
        return "00:00"
    return seconds_to_mmss(getattr(audio.info, "length", 0))


def get_tag_values_case_insensitive(tags, target: str):
    target_n = normalize_tag_name(target)
    for key, values in tags.items():
        if normalize_tag_name(str(key)) == target_n:
            return key, values
    return None, None


def custom_tag_checked(path: Path, tag_name: str) -> bool:
    audio = load_raw_tags(path)
    # A tagless file is falsy in mutagen, so compare against None explicitly.
    if audio is None or not audio.tags:
        return False

    if isinstance(audio.tags, ID3):
        for frame in audio.tags.getall("TXXX"):
            if normalize_tag_name(frame.desc) == normalize_tag_name(tag_name):
                values = [str(v) for v in frame.text]
                if any(v == "X" for v in values):
                    return True
        return False

    key, values = get_tag_values_case_insensitive(audio.tags, tag_name)
    if not key or not values:
        return False
    return any(str(v) == "X" for v in values)


def set_custom_tag(path: Path, tag_name: str, checked: bool):
    audio = load_raw_tags(path)
    if audio is None:
        return

    tag_name = ascii_tag_key(tag_name)

    if audio.tags is None:
        audio.add_tags()

    if isinstance(audio.tags, ID3):
        for frame in list(audio.tags.getall("TXXX")):
            if normalize_tag_name(frame.desc) == normalize_tag_name(tag_name):
                audio.tags.delall(f"TXXX:{frame.desc}")
        if checked:
            audio.tags.add(TXXX(encoding=3, desc=tag_name, text=["X"]))
        audio.save()
        return

    existing_key, _ = get_tag_values_case_insensitive(audio.tags, tag_name)
    if existing_key is not None:
        del audio.tags[existing_key]
    if checked:
        audio.tags[tag_name] = ["X"]
    audio.save()


@dataclass
class Playlist:
    name: str
    file_name: str
    tracks: List[str] = field(default_factory=list)


class SeekSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            value = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / max(1, self.width())
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
        super().mousePressEvent(event)


class TagCheckItem(QTableWidgetItem):
    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            return int(self.checkState() == Qt.Checked) < int(other.checkState() == Qt.Checked)
        return super().__lt__(other)


class PlaylistTable(QTableWidget):
    def __init__(self, on_files_dropped, on_delete_pressed, parent=None):
        super().__init__(parent)
        self.on_files_dropped = on_files_dropped
        self.on_delete_pressed = on_delete_pressed
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and not event.modifiers():
            self.on_delete_pressed()
            return
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                local = Path(url.toLocalFile())
                if local.suffix.lower() in AUDIO_EXTENSIONS:
                    paths.append(str(local))
        if paths:
            self.on_files_dropped(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tag GUI")
        self.data_dir = app_data_dir()
        self.custom_tags_file = self.data_dir / "custom_tags.txt"
        self.playlists_file = self.data_dir / "playlists.json"

        self.custom_tags: List[str] = []
        self.playlists: List[Playlist] = []
        self.current_track_index = -1
        self._updating_table = False

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        self.tabs = QTabWidget()
        self.tabs.setMovable(True)
        self.tabs.tabBarDoubleClicked.connect(self.on_tabbar_double_clicked)
        self.tabs.currentChanged.connect(self.on_tab_changed)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Custom checkbox tags (comma separated)")
        apply_tags_button = QPushButton("Apply Tags")
        apply_tags_button.clicked.connect(self.apply_custom_tags)

        controls = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        self.next_btn = QPushButton("Next")
        self.add_btn = QPushButton("Add Files")
        self.rename_btn = QPushButton("Rename / Save As")

        self.prev_btn.clicked.connect(self.play_previous)
        self.play_btn.clicked.connect(self.play_current_or_selected)
        self.pause_btn.clicked.connect(self.player.pause)
        self.stop_btn.clicked.connect(self.player.stop)
        self.next_btn.clicked.connect(self.play_next)
        self.add_btn.clicked.connect(self.add_files_dialog)
        self.rename_btn.clicked.connect(self.rename_playlist)

        for btn in [
            self.prev_btn,
            self.play_btn,
            self.pause_btn,
            self.stop_btn,
            self.next_btn,
            self.add_btn,
            self.rename_btn,
        ]:
            controls.addWidget(btn)

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
        table.setSortingEnabled(True)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setStyleSheet(SELECTION_STYLE)
        table.horizontalHeader().setSectionsMovable(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.verticalHeader().setVisible(False)
        table.itemDoubleClicked.connect(self.on_item_double_clicked)
        table.itemChanged.connect(self.on_item_changed)
        return table

    def on_tabbar_double_clicked(self, index):
        if index != -1:
            return
        name, file_name = self.next_default_playlist_name()
        playlist = Playlist(name=name, file_name=file_name, tracks=[])
        self.playlists.append(playlist)
        table = self.create_table()
        self.tabs.addTab(table, playlist.name)
        self.populate_table(table, playlist)
        self.tabs.setCurrentWidget(table)
        self.save_state()

    def on_tab_changed(self, _index):
        self.current_track_index = -1

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
        self.save_state()

    def save_state(self):
        for playlist in self.playlists:
            self.save_playlist_file(playlist)
        state = {
            "active_index": self.tabs.currentIndex(),
            "playlists": [{"name": p.name, "file_name": p.file_name} for p in self.playlists],
        }
        self.playlists_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def apply_custom_tags(self):
        self.custom_tags = parse_custom_tags(self.tags_input.text())
        self.save_custom_tags()
        for idx, playlist in enumerate(self.playlists):
            table = self.tabs.widget(idx)
            self.populate_table(table, playlist)
        self.save_state()

    def track_metadata(self, path: str):
        p = Path(path)
        easy = load_easy_tags(p)
        artist = get_field(easy, "artist") if easy else ""
        title = get_field(easy, "title") if easy else ""
        album = get_field(easy, "album") if easy else ""
        date = get_field(easy, "date") if easy else ""
        year = date[:4] if date else ""
        duration = get_duration(p)
        return [artist, title or p.stem, album, year, duration]

    def populate_table(self, table: PlaylistTable, playlist: Playlist):
        self._updating_table = True
        try:
            headers = DEFAULT_COLUMNS + self.custom_tags
            table.clear()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.setRowCount(len(playlist.tracks))

            for row, track in enumerate(playlist.tracks):
                fields = self.track_metadata(track)
                for col, value in enumerate(fields):
                    item = QTableWidgetItem(value)
                    if col == 0:
                        item.setData(Qt.UserRole, track)
                    table.setItem(row, col, item)

                for offset, tag in enumerate(self.custom_tags):
                    col = len(DEFAULT_COLUMNS) + offset
                    checked = custom_tag_checked(Path(track), tag)
                    item = TagCheckItem()
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                    item.setData(Qt.UserRole, track)
                    item.setData(Qt.UserRole + 1, tag)
                    table.setItem(row, col, item)
            table.resizeColumnsToContents()
        finally:
            self._updating_table = False

    def add_tracks_to_current_playlist(self, paths: List[str]):
        playlist = self.current_playlist()
        for p in paths:
            if p not in playlist.tracks:
                playlist.tracks.append(p)
        table = self.current_table()
        self.populate_table(table, playlist)
        self.save_state()

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            "",
            "Audio files (*.mp3 *.flac)",
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

    def play_current_or_selected(self):
        table = self.current_table()
        selected = table.currentRow()
        if selected >= 0:
            self.play_row(selected)
        elif self.current_track_index >= 0:
            self.play_row(self.current_track_index)
        elif self.current_playlist().tracks:
            self.play_row(0)

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
        super().closeEvent(event)


def main():
    if sys.platform == "win32":
        # Without an explicit AppUserModelID Windows shows the host python.exe icon in the taskbar.
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv)
    app.setWindowIcon(note_icon())
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
