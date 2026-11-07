"""Reads track numbers missing from the tag cache in the background and fills the Track column.

Caches written before the Track column only hold track numbers for playlists that were once
sorted by year. Reading the rest at startup would block it for minutes on a big library, so
the window opens from the cache and the numbers arrive in batches.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from ..constants import TRACK_COLUMN
from ..core.metadata import track_text
from ..core.tags import read_track_position
from .table_fill import rows_by_track
from .window_base import WindowContext

BATCH_SIZE = 200

Position = Tuple[int, int]


class TrackNumberWorker(QThread):
    batch_read = Signal(object)  # {track: (disc, track)}

    def __init__(self, tracks: List[str], parent=None):
        super().__init__(parent)
        self._tracks = tracks

    def run(self):
        batch: Dict[str, Position] = {}
        for track in self._tracks:
            if self.isInterruptionRequested():
                return
            batch[track] = read_track_position(Path(track))
            if len(batch) >= BATCH_SIZE:
                self.batch_read.emit(batch)
                batch = {}
        if batch:
            self.batch_read.emit(batch)


class TrackNumbersMixin(WindowContext):
    _track_number_worker: Optional[TrackNumberWorker] = None

    def fill_missing_track_numbers(self):
        missing = self.metadata.tracks_without_position(
            track for playlist in self.playlists for track in playlist.tracks
        )
        if not missing or self._track_number_worker is not None:
            return
        worker = TrackNumberWorker(missing, self)
        # A bound method, not a lambda, so Qt queues the call onto the UI thread.
        worker.batch_read.connect(self.on_track_numbers_read)
        worker.finished.connect(self._on_track_numbers_finished)
        self._track_number_worker = worker
        worker.start()

    def on_track_numbers_read(self, positions: Dict[str, Position]):
        for track, position in positions.items():
            self.metadata.remember_position(track, position)
        self.show_track_numbers(positions)

    def show_track_numbers(self, positions: Dict[str, Position]):
        self._updating_table = True
        try:
            for index in range(self.tabs.count()):
                table = self.tabs.widget(index)
                rows = rows_by_track(table)
                for track, (_disc, number) in positions.items():
                    row = rows.get(track)
                    item = table.item(row, TRACK_COLUMN) if row is not None else None
                    if item is not None:
                        item.setText(track_text(number))
        finally:
            self._updating_table = False

    def _on_track_numbers_finished(self):
        worker = self._track_number_worker
        self._track_number_worker = None
        if worker is not None:
            worker.deleteLater()

    def stop_track_numbers(self):
        """Called on close; numbers read so far are already in the cache."""
        worker = self._track_number_worker
        if worker is None:
            return
        worker.batch_read.disconnect()
        worker.requestInterruption()
        worker.wait()
        self._track_number_worker = None
