"""Deciding when a play counts as a Last.fm scrobble.

Last.fm's rule: the track is longer than 30 seconds and has been played for half its length
or 4 minutes, whichever comes first. Only time actually spent playing counts, so pausing
or skipping forward does not make a track count sooner.
"""

import time
from typing import Callable, Optional

MIN_TRACK_MS = 30_000
MAX_NEEDED_MS = 240_000


def needed_ms(duration_ms: int) -> Optional[int]:
    """How long a track must play to count, or None when it is too short to ever count."""
    if duration_ms <= MIN_TRACK_MS:
        return None
    return min(duration_ms // 2, MAX_NEEDED_MS)


class ListenTracker:
    """Wall-clock listening time for the current play, with a clock tests can replace."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self.track: Optional[str] = None
        self.started_at = 0
        self.duration_ms = 0
        self._listened = 0.0
        self._resumed_at: Optional[float] = None
        self.counted = False

    def start(self, track: str, started_at: int):
        """A new play of ``track``; ``started_at`` is the Unix time Last.fm records."""
        self.track = track
        self.started_at = started_at
        self.duration_ms = 0
        self._listened = 0.0
        self._resumed_at = None
        self.counted = False

    def set_duration(self, duration_ms: int):
        self.duration_ms = max(0, duration_ms)

    def resume(self):
        if self.track is not None and self._resumed_at is None:
            self._resumed_at = self._clock()

    def pause(self):
        if self._resumed_at is not None:
            self._listened += self._clock() - self._resumed_at
            self._resumed_at = None

    def listened_ms(self) -> int:
        running = self._clock() - self._resumed_at if self._resumed_at is not None else 0.0
        return int((self._listened + running) * 1000)

    def discard(self):
        """The current play will never count, however long it keeps playing."""
        self.counted = True

    def take_scrobble(self) -> bool:
        """True exactly once per play, as soon as the play has become a scrobble."""
        if self.counted or self.track is None:
            return False
        needed = needed_ms(self.duration_ms)
        if needed is None or self.listened_ms() < needed:
            return False
        self.counted = True
        return True
