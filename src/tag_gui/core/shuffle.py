"""Picking the next track for shuffle play, steering clear of recently heard music.

A candidate clashes with a recently played track when it shares the artist, the album or the
song. Songs are compared fuzzily, so "Song (Cover)", "Song - Live 2018" and "Song" count as
the same song.
"""

import random
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Dict, Optional, Sequence, Set

RECENT_LIMIT = 10
# Titles at least this similar after normalizing are treated as the same song.
TITLE_SIMILARITY = 0.88

_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")
# Trailing qualifiers after a dash, e.g. "Song - Remastered 2011" or "Song - Radio Edit".
_DASH_SUFFIX = re.compile(r"\s+[-\u2013\u2014/]\s+.*$")
_VERSION_WORDS = (
    r"live|remaster(?:ed)?|demo|acoustic|unplugged|cover|instrumental|edit|radio edit"
    r"|single version|album version|version|mono|stereo|remix|mix|bonus track|re-?recorded"
)
# A qualifier at the end, optionally with a year or venue: "Song Live 2018", "Song Live at X".
_TRAILING_QUALIFIER = re.compile(
    rf"\s+(?:{_VERSION_WORDS})(?:\s+(?:at|in|from|on)\b.*|\s+\d{{2,4}}\b.*)?$"
)
_NON_WORD = re.compile(r"[^\w]+")


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return stripped.casefold().strip()


def normalize_name(text: str) -> str:
    """Artist and album names: case, accents and punctuation do not matter."""
    return _NON_WORD.sub(" ", _plain(text)).strip()


def normalize_title(title: str) -> str:
    """The core of a song title, without version notes like "(Cover)" or "Live 2018"."""
    text = _BRACKETED.sub(" ", _plain(title))
    text = _DASH_SUFFIX.sub("", text)
    text = _NON_WORD.sub(" ", text).strip()
    while True:
        shorter = _TRAILING_QUALIFIER.sub("", text).strip()
        # Never strip a title down to nothing, e.g. a song simply called "Live".
        if shorter == text or not shorter:
            return text
        text = shorter


def same_title(first: str, second: str) -> bool:
    if not first or not second:
        return False
    if first == second:
        return True
    matcher = SequenceMatcher(None, first, second)
    return matcher.quick_ratio() >= TITLE_SIMILARITY and matcher.ratio() >= TITLE_SIMILARITY


@dataclass(frozen=True)
class TrackKey:
    artist: str
    album: str
    title: str

    @classmethod
    def of(cls, artist: str, album: str, title: str) -> "TrackKey":
        return cls(normalize_name(artist), normalize_name(album), normalize_title(title))

    def clashes_with(self, other: "TrackKey") -> bool:
        if self.artist and self.artist == other.artist:
            return True
        if self.album and self.album == other.album:
            return True
        return same_title(self.title, other.title)


def pick_next(
    candidates: Sequence[str],
    key_of: Callable[[str], TrackKey],
    recent: Sequence[str],
    played: Optional[Set[str]] = None,
    rng: Optional[random.Random] = None,
) -> Optional[str]:
    """A random candidate that does not clash with the ``recent`` tracks (newest last).

    Tracks not yet ``played`` in this shuffle round are preferred. When every candidate clashes,
    fewer of the recent tracks are considered step by step, so a small or single-artist
    playlist still plays on instead of stopping.
    """
    if not candidates:
        return None
    rng = rng or random
    played = played or set()
    keys: Dict[str, TrackKey] = {}

    def key(track: str) -> TrackKey:
        if track not in keys:
            keys[track] = key_of(track)
        return keys[track]

    order = list(candidates)
    rng.shuffle(order)
    unplayed = [track for track in order if track not in played]
    already_played = [track for track in order if track in played]
    history = list(recent[-RECENT_LIMIT:])

    for window in range(len(history), 0, -1):
        considered = history[len(history) - window :]
        avoided = set(considered)
        recent_keys = [key(track) for track in considered]
        for pool in (unplayed, already_played):
            for track in pool:
                if track in avoided:
                    continue
                candidate = key(track)
                if not any(candidate.clashes_with(other) for other in recent_keys):
                    return track
    # Everything clashes: at least do not repeat the track that just played.
    last = history[-1] if history else None
    for pool in (unplayed, already_played):
        for track in pool:
            if track != last:
                return track
    return order[0]
