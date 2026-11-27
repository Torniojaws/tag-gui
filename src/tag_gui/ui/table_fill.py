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
    TRACK_COLUMN,
    YEAR_COLUMN,
)
from ..core.metadata import MetadataCache
from ..core.models import Playlist
from .styles import DURATION_COLUMN_PADDING
from .table import NumberItem, PlaylistTable, TagCheckItem

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


def rows_of_track(table: PlaylistTable, track: str) -> List[int]:
    """Every row showing ``track``, searched inside Qt.

    Runs on each checkbox click for every playlist, where a Python loop over the rows of a
    big playlist would be felt.
    """
    model = table.model()
    start = model.index(0, PATH_COLUMN)
    return [index.row() for index in model.match(start, Qt.UserRole, track, -1, Qt.MatchExactly)]


def show_tag_state(table: PlaylistTable, track: str, column: int, checked: bool) -> None:
    """Make the checkbox in ``column`` show a state that was written from another playlist."""
    state = Qt.Checked if checked else Qt.Unchecked
    for row in rows_of_track(table, track):
        item = table.item(row, column)
        if item is not None and item.checkState() != state:
            item.setCheckState(state)


def selected_tracks(table: PlaylistTable) -> List[str]:
    """Selected tracks, leaving out rows hidden by the filter (Ctrl+A still selects those)."""
    tracks = []
    seen = set()
    for row in sorted({index.row() for index in table.selectedIndexes()}):
        if table.isRowHidden(row):
            continue
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
    item = NumberItem(value) if column == TRACK_COLUMN else QTableWidgetItem(value)
    # Standard tags are edited through the right-click dialog, never inline.
    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
    if column in (YEAR_COLUMN, TRACK_COLUMN):
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


def _fill_row(
    table: PlaylistTable,
    row: int,
    track: str,
    custom_tags: Sequence[str],
    metadata: MetadataCache,
) -> None:
    info = metadata.get(track, custom_tags)
    for col, value in enumerate(info.fields):
        table.setItem(row, col, _field_item(value, col, track))
    for offset, tag in enumerate(custom_tags):
        column = len(DEFAULT_COLUMNS) + offset
        table.setItem(row, column, _tag_item(track, tag, bool(info.tag_states.get(tag))))


def _fit_columns(table: PlaylistTable) -> None:
    table.resizeColumnsToContents()
    width = table.fontMetrics().horizontalAdvance("00:00") + DURATION_COLUMN_PADDING
    table.setColumnWidth(DURATION_COLUMN, width)


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
        _fill_row(table, row, track, custom_tags, metadata)

    table.reapply_sort()
    table.refresh_filter()
    table.apply_album_colors()
    _fit_columns(table)


def append_rows(
    table: PlaylistTable,
    tracks: Sequence[str],
    custom_tags: Sequence[str],
    metadata: MetadataCache,
    on_progress=None,
) -> None:
    """Add rows for ``tracks`` below the existing ones, which keep their place and shade.

    Rebuilding the table would re-run the header sort; rows that moved since the last sort,
    like ones whose tag checkbox was clicked, would jump and flip the album shades.
    """
    first = table.rowCount()
    table.setRowCount(first + len(tracks))
    for offset, track in enumerate(tracks):
        if on_progress and offset % POPULATE_BATCH == 0:
            on_progress(offset)
        _fill_row(table, first + offset, track, custom_tags, metadata)

    table.refresh_filter()
    table.apply_album_colors(first)
    _fit_columns(table)


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
    shown = [track for track in tracks if track in rows]
    if not shown:
        return
    for track in shown:
        row = rows[track]
        info = metadata.get(track, custom_tags)
        for col, value in enumerate(info.fields):
            item = table.item(row, col)
            if item:
                item.setText(value)
        for offset, tag in enumerate(custom_tags):
            item = table.item(row, len(DEFAULT_COLUMNS) + offset)
            checked = Qt.Checked if info.tag_states.get(tag) else Qt.Unchecked
            if item and item.checkState() != checked:
                item.setCheckState(checked)
    table.apply_album_colors()
    table.refresh_filter()
