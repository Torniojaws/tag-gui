"""Reordering a playlist's tracks: by path, randomly, or by release year."""

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class SortFields:
    year: str
    album: str
    title: str
    disc: int = 0
    track: int = 0


def by_path(tracks: Sequence[str]) -> List[str]:
    return sorted(tracks, key=lambda path: (path.casefold(), path))


def shuffled(tracks: Sequence[str], rng: Optional[random.Random] = None) -> List[str]:
    result = list(tracks)
    (rng or random).shuffle(result)
    return result


def _year(value: str) -> Optional[int]:
    value = value.strip()
    return int(value[:4]) if len(value) >= 4 and value[:4].isdigit() else None


def _within_album(path: str, fields: SortFields) -> Tuple:
    # Numbered tracks come first in disc/track order, the rest by title and then by path.
    numbered = fields.track > 0
    return (
        not numbered,
        fields.disc if numbered else 0,
        fields.track,
        fields.title.casefold(),
        path.casefold(),
        path,
    )


def by_year(
    tracks: Sequence[str], fields_of: Callable[[str], SortFields], newest_first: bool = False
) -> List[str]:
    """Group tracks into releases and order the releases by year.

    A release is the tracks sharing a year and an album name. Releases of the same year keep
    the order in which they first appear in the playlist, and tracks without a year go last.
    A track without an album tag is a release of its own.
    """
    releases: Dict[Tuple, List[Tuple[str, SortFields]]] = {}
    for path in tracks:
        fields = fields_of(path)
        album = fields.album.strip().casefold()
        key = (_year(fields.year), album) if album else (_year(fields.year), None, path)
        releases.setdefault(key, []).append((path, fields))

    def release_order(key: Tuple) -> Tuple[bool, int]:
        year = key[0]
        if year is None:
            return True, 0
        return False, -year if newest_first else year

    # sorted() is stable, so releases of the same year stay in their first-appearance order.
    ordered = []
    for key in sorted(releases, key=release_order):
        members = sorted(releases[key], key=lambda item: _within_album(*item))
        ordered.extend(path for path, _fields in members)
    return ordered
