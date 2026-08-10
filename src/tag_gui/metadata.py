from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence

from .tags import get_duration, get_field, load_easy_tags, read_custom_tag_states


def track_fields(path: Path) -> List[str]:
    easy = load_easy_tags(path)
    artist = get_field(easy, "artist") if easy else ""
    title = get_field(easy, "title") if easy else ""
    album = get_field(easy, "album") if easy else ""
    date = get_field(easy, "date") if easy else ""
    year = date[:4] if date else ""
    return [artist, title or path.stem, album, year, get_duration(path)]


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


class MetadataCache:
    """Keeps tags read from disk so redrawing a playlist does not reopen every file."""

    def __init__(self):
        self._entries: Dict[str, TrackInfo] = {}

    def get(self, track: str, tag_names: Sequence[str]) -> TrackInfo:
        path = Path(track)
        mtime = file_mtime(path)
        info = self._entries.get(track)

        if info is None or info.mtime != mtime:
            info = TrackInfo(
                fields=track_fields(path),
                mtime=mtime,
                tag_states=read_custom_tag_states(path, tag_names),
            )
            self._entries[track] = info
            return info

        missing = [tag for tag in tag_names if tag not in info.tag_states]
        if missing:
            info.tag_states.update(read_custom_tag_states(path, missing))
        return info

    def update_tag_state(self, track: str, tag: str, checked: bool) -> None:
        """Called after a successful write so the changed file is not re-read."""
        info = self._entries.get(track)
        if info is None:
            return
        info.tag_states[tag] = checked
        info.mtime = file_mtime(Path(track))

    def discard(self, track: str) -> None:
        self._entries.pop(track, None)
