"""The sort dropdown that reorders the current playlist, with a busy/done note beside it."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ..constants import ALBUM_COLUMN, SONG_COLUMN, YEAR_COLUMN
from ..core.models import Playlist
from ..core.sorting import SortFields, by_path, by_year, shuffled
from ..core.tags import read_track_position
from .spinner import Spinner
from .styles import SORT_DONE_COLOR, SORT_DONE_FADE_MS, SORT_DONE_VISIBLE_MS
from .table_fill import row_for_path
from .window_base import WindowContext

SORT_BY_PATH = "path"
SORT_RANDOM = "random"
SORT_OLDEST = "oldest"
SORT_NEWEST = "newest"
SORT_OPTIONS = (
    (SORT_BY_PATH, "Sort by full file path"),
    (SORT_RANDOM, "Sort randomly"),
    (SORT_OLDEST, "Sort releases by year (oldest first)"),
    (SORT_NEWEST, "Sort releases by year (newest first)"),
)
PROGRESS_EVERY = 10

Position = Tuple[int, int]


class YearSortWorker(QThread):
    """Reads the track numbers not cached yet and orders the tracks, off the UI thread.

    Opening a file can take ~10 ms on slow or network disks, so a large playlist that was
    never sorted before needs minutes of reads. Only plain data crosses the thread boundary.
    """

    progress = Signal(int, int)
    done = Signal(object, object)  # ordered tracks, {track: position} newly read

    def __init__(
        self,
        tracks: List[str],
        fields: Dict[str, Tuple[str, str, str]],
        positions: Dict[str, Optional[Position]],
        newest_first: bool,
        parent=None,
    ):
        super().__init__(parent)
        self._tracks = tracks
        self._fields = fields
        self._positions = dict(positions)
        self._newest_first = newest_first

    def run(self):
        missing = [track for track, pos in self._positions.items() if pos is None]
        read: Dict[str, Position] = {}
        for count, track in enumerate(missing):
            if self.isInterruptionRequested():
                return
            if count % PROGRESS_EVERY == 0:
                self.progress.emit(count, len(missing))
            read[track] = read_track_position(Path(track))
        self._positions.update(read)

        def fields_of(track: str) -> SortFields:
            year, album, title = self._fields[track]
            disc, number = self._positions[track] or (0, 0)
            return SortFields(year=year, album=album, title=title, disc=disc, track=number)

        order = by_year(self._tracks, fields_of, newest_first=self._newest_first)
        if not self.isInterruptionRequested():
            self.done.emit(order, read)


class SortMixin(WindowContext):
    def _build_sort_controls(self) -> QWidget:
        self.sort_combo = QComboBox()
        self.sort_combo.setPlaceholderText("Sort playlist...")
        for mode, label in SORT_OPTIONS:
            self.sort_combo.addItem(label, mode)
        self.sort_combo.setCurrentIndex(-1)
        self.sort_combo.activated.connect(self.on_sort_chosen)
        self._sort_worker: Optional[YearSortWorker] = None
        self._sorting_playlist: Optional[Playlist] = None

        self.sort_spinner = Spinner()
        self.sort_status = QLabel()
        self.sort_note = QWidget()
        note_layout = QHBoxLayout(self.sort_note)
        note_layout.setContentsMargins(0, 0, 0, 0)
        note_layout.addWidget(self.sort_spinner, 0, Qt.AlignVCenter)
        note_layout.addWidget(self.sort_status, 0, Qt.AlignVCenter)
        self._sort_note_effect = QGraphicsOpacityEffect(self.sort_note)
        self.sort_note.setGraphicsEffect(self._sort_note_effect)
        self.sort_note.hide()

        self._sort_done_timer = QTimer(self)
        self._sort_done_timer.setSingleShot(True)
        self._sort_done_timer.setInterval(SORT_DONE_VISIBLE_MS)
        self._sort_done_fade = QPropertyAnimation(self._sort_note_effect, b"opacity", self)
        self._sort_done_fade.setDuration(SORT_DONE_FADE_MS)
        self._sort_done_fade.setStartValue(1.0)
        self._sort_done_fade.setEndValue(0.0)
        self._sort_done_fade.setEasingCurve(QEasingCurve.InOutQuad)
        self._sort_done_timer.timeout.connect(self._sort_done_fade.start)
        self._sort_done_fade.finished.connect(self.sort_note.hide)

        controls = QWidget()
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sort_combo, 0, Qt.AlignVCenter)
        layout.addWidget(self.sort_note, 0, Qt.AlignVCenter)
        return controls

    def on_sort_chosen(self, index: int):
        mode = self.sort_combo.itemData(index)
        self.sort_combo.setCurrentIndex(-1)
        table = self.current_table()
        if table is not None:
            table.setFocus()
        if mode:
            self.sort_current_playlist(mode)

    def is_sorting(self) -> bool:
        return self._sort_worker is not None

    def sort_current_playlist(self, mode: str):
        """Reorder only the current playlist. Year sorts run in the background."""
        if self.tabs.currentIndex() < 0 or self.is_sorting():
            return
        playlist = self.current_playlist()
        if mode == SORT_BY_PATH:
            self.apply_playlist_order(playlist, by_path(playlist.tracks))
        elif mode == SORT_RANDOM:
            self.apply_playlist_order(playlist, shuffled(playlist.tracks))
        elif mode in (SORT_OLDEST, SORT_NEWEST):
            self.start_year_sort(playlist, newest_first=mode == SORT_NEWEST)

    def start_year_sort(self, playlist: Playlist, newest_first: bool):
        tracks = list(playlist.tracks)
        fields = {}
        positions = {}
        for track in tracks:
            info = self.metadata.get(track, self.custom_tags).fields
            fields[track] = (info[YEAR_COLUMN], info[ALBUM_COLUMN], info[SONG_COLUMN])
            positions[track] = self.metadata.cached_position(track)

        worker = YearSortWorker(tracks, fields, positions, newest_first, self)
        # Bound methods, not lambdas, so Qt queues the calls onto the UI thread.
        worker.progress.connect(self.on_sort_progress)
        worker.done.connect(self.on_year_sort_done)
        worker.finished.connect(worker.deleteLater)
        self._sort_worker = worker
        self._sorting_playlist = playlist
        self.sort_combo.setEnabled(False)
        self.show_sort_busy("Sorting...")
        worker.start()

    def on_sort_progress(self, done: int, total: int):
        self.show_sort_busy(f"Reading track numbers... {done} / {total}")

    def on_year_sort_done(self, order: List[str], read: Dict[str, Position]):
        playlist = self._sorting_playlist
        self._sort_worker = None
        self._sorting_playlist = None
        self.sort_combo.setEnabled(True)
        for track, position in read.items():
            self.metadata.remember_position(track, position)
        self.apply_playlist_order(playlist, order)

    def cancel_sorting(self):
        """Stop a background sort, e.g. when the window closes; its result is dropped."""
        worker = self._sort_worker
        if worker is None:
            return
        self._sort_worker = None
        self._sorting_playlist = None
        worker.done.disconnect()
        worker.requestInterruption()
        worker.wait()
        self.sort_combo.setEnabled(True)
        self.sort_spinner.stop()
        self.sort_note.hide()

    def apply_playlist_order(self, playlist: Playlist, order: List[str]):
        index = next((i for i, p in enumerate(self.playlists) if p is playlist), -1)
        if index < 0:
            # The playlist was removed while it was being sorted.
            self.sort_spinner.stop()
            self.sort_note.hide()
            return
        # Tracks added or removed during a background sort are kept or dropped, not lost.
        present = set(playlist.tracks)
        ordered = [track for track in order if track in present]
        placed = set(ordered)
        ordered += [track for track in playlist.tracks if track not in placed]
        playlist.tracks = ordered

        table = self.tabs.widget(index)
        table.reorder(ordered)
        if table is self.current_table():
            playing = self.player.source().toLocalFile()
            self.current_track_index = row_for_path(table, playing) if playing else -1
        table.scrollToTop()
        self.save_state()
        self.show_sort_done()

    def show_sort_busy(self, text: str):
        self._sort_done_timer.stop()
        self._sort_done_fade.stop()
        self._sort_note_effect.setOpacity(1.0)
        self.sort_status.setStyleSheet("")
        self.sort_status.setText(text)
        if not self.sort_spinner.is_spinning():
            self.sort_spinner.start()
        self.sort_note.show()

    def show_sort_done(self):
        self.sort_spinner.stop()
        self._sort_done_fade.stop()
        self._sort_note_effect.setOpacity(1.0)
        self.sort_status.setStyleSheet(f"color: {SORT_DONE_COLOR};")
        self.sort_status.setText("\u2714 Sorting completed")
        self.sort_note.show()
        self._sort_done_timer.start()
