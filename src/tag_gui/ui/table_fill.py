"""Filling playlist tables from the metadata cache."""

from pathlib import Path
from typing import Dict, List, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem

from ..constants import (
    DEFAULT_COLUMNS,
    DURATION_COLUMN,
    LEFT_ALIGNED_HEADERS,
    PATH_COLUMN,
    POPULATE_BATCH,
    YEAR_COLUMN,
)
from ..core.metadata import MetadataCache
from ..core.models import Playlist
from .styles import DURATION_COLUMN_PADDING
from .table import PlaylistTable, TagCheckItem

TAG_NAME_ROLE = Qt.UserRole + 1


def track_of(item) -> str:
    return item.data(Qt.UserRole) if item else ""


def rows_by_track(table: PlaylistTable) -> Dict[str, int]:
    rows = {}
    for row in range(table.rowCount()):
        track = track_of(table.item(row, PATH_COLUMN))
        if track:
            rows[track] = row
    return rows


def selected_tracks(table: PlaylistTable) -> List[str]:
    tracks = []
    seen = set()
    for row in sorted({index.row() for index in table.selectedIndexes()}):
        track = track_of(table.item(row, PATH_COLUMN))
        if track and track not in seen:
            seen.add(track)
            tracks.append(track)
    return tracks


def row_for_path(table: PlaylistTable, path: str) -> int:
    if not path:
        return -1
    target = Path(path)
    for row in range(table.rowCount()):
        stored = track_of(table.item(row, PATH_COLUMN))
        if stored and Path(stored) == target:
            return row
    return -1


def _set_headers(table: PlaylistTable, custom_tags: Sequence[str]) -> None:
    headers = DEFAULT_COLUMNS + list(custom_tags)
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    for col in LEFT_ALIGNED_HEADERS:
        header_item = table.horizontalHeaderItem(col)
        if header_item:
            header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)


def _field_item(value: str, column: int, track: str) -> QTableWidgetItem:
    item = QTableWidgetItem(value)
    # Standard tags are edited through the right-click dialog, never inline.
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    if column == YEAR_COLUMN:
        item.setTextAlignment(Qt.AlignCenter)
    elif column == DURATION_COLUMN:
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if column == PATH_COLUMN:
        item.setData(Qt.UserRole, track)
    return item


def _tag_item(track: str, tag: str, checked: bool) -> TagCheckItem:
    item = TagCheckItem()
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
    item.setTextAlignment(Qt.AlignCenter)
    item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
    item.setData(Qt.UserRole, track)
    item.setData(TAG_NAME_ROLE, tag)
    return item


def fill_table(
    table: PlaylistTable,
    playlist: Playlist,
    custom_tags: Sequence[str],
    metadata: MetadataCache,
    on_progress=None,
) -> None:
    _set_headers(table, custom_tags)
    table.setRowCount(len(playlist.tracks))

    for row, track in enumerate(playlist.tracks):
        if on_progress and row % POPULATE_BATCH == 0:
            on_progress(row)
        info = metadata.get(track, custom_tags)
        for col, value in enumerate(info.fields):
            table.setItem(row, col, _field_item(value, col, track))
        for offset, tag in enumerate(custom_tags):
            column = len(DEFAULT_COLUMNS) + offset
            table.setItem(row, column, _tag_item(track, tag, bool(info.tag_states.get(tag))))

    table.reapply_sort()
    table.apply_album_colors()
    table.resizeColumnsToContents()
    width = table.fontMetrics().horizontalAdvance("00:00") + DURATION_COLUMN_PADDING
    table.setColumnWidth(DURATION_COLUMN, width)


def refresh_rows(
    table: PlaylistTable,
    tracks: Sequence[str],
    custom_tags: Sequence[str],
    metadata: MetadataCache,
) -> None:
    """Re-read only the given tracks instead of rebuilding the whole table."""
    if not tracks:
        return
    rows = rows_by_track(table)
    for track in tracks:
        row = rows.get(track)
        if row is None:
            continue
        info = metadata.get(track, custom_tags)
        for col, value in enumerate(info.fields):
            item = table.item(row, col)
            if item:
                item.setText(value)
    table.apply_album_colors()
