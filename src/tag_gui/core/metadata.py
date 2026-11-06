import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .tags import (
    get_duration,
    get_field,
    load_easy_tags,
    position_from_tags,
    read_custom_tag_states,
    read_track_position,
)

# Bumped whenever the field order changes, so stale entries are discarded.
CACHE_VERSION = 2


def track_fields(path: Path, easy=None) -> List[str]:
    """Values in DEFAULT_COLUMNS order. ``easy`` reuses tags the caller already loaded."""
    if easy is None:
        easy = load_easy_tags(path)
    artist = get_field(easy, "artist") if easy else ""
    title = get_field(easy, "title") if easy else ""
    album = get_field(easy, "album") if easy else ""
    date = get_field(easy, "date") if easy else ""
    year = date[:4] if date else ""
    return [artist, get_duration(path), title or path.stem, year, album]


def file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


@dataclass
class TrackInfo:
    fields: List[str]
    mtime: float
    tag_states: Dict[str, bool] = field(default_factory=dict)
    # (disc, track); None for entries cached before positions were stored.
    position: Optional[Tuple[int, int]] = None


class MetadataCache:
    """Keeps tags read from disk, in memory and in a JSON file between sessions."""

    def __init__(self, path: Optional[Path] = None):
        self._entries: Dict[str, TrackInfo] = {}
        self._path = path
        self._dirty = False

    def get(self, track: str, tag_names: Sequence[str]) -> TrackInfo:
        path = Path(track)
        mtime = file_mtime(path)
        info = self._entries.get(track)

        if info is None or info.mtime != mtime:
            # Opening a file can take ~10 ms on slow disks, so the track position is read
            # along with the fields instead of separately when a sort needs it.
            easy = load_easy_tags(path)
            info = TrackInfo(
                fields=track_fields(path, easy),
                mtime=mtime,
                tag_states=read_custom_tag_states(path, tag_names),
                position=position_from_tags(easy),
            )
            self._entries[track] = info
            self._dirty = True
            return info

        missing = [tag for tag in tag_names if tag not in info.tag_states]
        if missing:
            info.tag_states.update(read_custom_tag_states(path, missing))
            self._dirty = True
        return info

    def track_position(self, track: str) -> Tuple[int, int]:
        info = self.get(track, ())
        if info.position is None:
            info.position = read_track_position(Path(track))
            self._dirty = True
        return info.position

    def cached_position(self, track: str) -> Optional[Tuple[int, int]]:
        info = self._entries.get(track)
        return info.position if info else None

    def remember_position(self, track: str, position: Tuple[int, int]) -> None:
        """Store a position read elsewhere, e.g. on a background thread."""
        info = self._entries.get(track)
        if info is not None and info.position != position:
            info.position = position
            self._dirty = True

    def update_tag_state(self, track: str, tag: str, checked: bool) -> None:
        """Called after a successful write so the changed file is not re-read."""
        info = self._entries.get(track)
        if info is None:
            return
        info.tag_states[tag] = checked
        info.mtime = file_mtime(Path(track))
        self._dirty = True

    def discard(self, track: str) -> None:
        if self._entries.pop(track, None) is not None:
            self._dirty = True

    def load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if data.get("version") != CACHE_VERSION:
            return
        for track, entry in data.get("tracks", {}).items():
            try:
                self._entries[track] = TrackInfo(
                    fields=[str(v) for v in entry["fields"]],
                    mtime=float(entry["mtime"]),
                    tag_states={str(k): bool(v) for k, v in entry.get("tags", {}).items()},
                    position=_position(entry.get("position")),
                )
            except (KeyError, TypeError, ValueError):
                continue

    def save(self, keep: Optional[Iterable[str]] = None) -> None:
        if self._path is None:
            return
        if keep is not None:
            wanted = set(keep)
            dropped = [track for track in self._entries if track not in wanted]
            for track in dropped:
                del self._entries[track]
            self._dirty = self._dirty or bool(dropped)
        if not self._dirty:
            return
        data = {
            "version": CACHE_VERSION,
            "tracks": {
                track: _entry(info) for track, info in self._entries.items()
            },
        }
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self._path)
        self._dirty = False


def _entry(info: TrackInfo) -> dict:
    entry = {"mtime": info.mtime, "fields": info.fields, "tags": info.tag_states}
    if info.position is not None:
        entry["position"] = list(info.position)
    return entry


def _position(value) -> Optional[Tuple[int, int]]:
    if value is None:
        return None
    disc, track = value
    return int(disc), int(track)
