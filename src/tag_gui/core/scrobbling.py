"""The scrobbling workflow behind the UI: tags in, Last.fm calls out, unsent plays kept.

ScrobbleService is called from a single worker thread. Plays that cannot be sent right now
(offline, Last.fm down, logged out) wait in a JSON file and go out with the next flush.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .lastfm import LastfmClient, LastfmError, Scrobble, chunks
from .tags import get_field, load_easy_tags, position_from_tags

# Last.fm ignores scrobbles older than two weeks, so there is no point keeping more.
MAX_PENDING = 5000


def read_scrobble_tags(path: Path, started_at: int, duration_s: int) -> Optional[Scrobble]:
    """A scrobble from the file's tags, or None without an artist and title tag.

    Last.fm asks clients never to guess these from file names.
    """
    easy = load_easy_tags(path)
    artist = get_field(easy, "artist").strip() if easy else ""
    title = get_field(easy, "title").strip() if easy else ""
    if not artist or not title:
        return None
    _disc, number = position_from_tags(easy)
    return Scrobble(
        artist=artist,
        track=title,
        timestamp=started_at,
        album=get_field(easy, "album").strip(),
        album_artist=get_field(easy, "albumartist").strip(),
        duration=max(0, duration_s),
        track_number=number,
    )


@dataclass
class FlushResult:
    sent: int = 0
    dropped: int = 0
    retry_later: bool = False
    session_lost: bool = False
    error: str = ""


TagReader = Callable[[Path, int, int], Optional[Scrobble]]


class ScrobbleService:
    def __init__(
        self,
        client: LastfmClient,
        queue_path: Optional[Path] = None,
        read_tags: Optional[TagReader] = None,
    ):
        self.client = client
        self.queue_path = queue_path
        self._read_tags = read_tags
        self.pending: List[Scrobble] = []
        self._load()

    def read_tags(self, path: Path, started_at: int, duration_s: int) -> Optional[Scrobble]:
        return (self._read_tags or read_scrobble_tags)(path, started_at, duration_s)

    @property
    def logged_in(self) -> bool:
        return bool(self.client.session_key)

    def set_session(self, session_key: Optional[str]):
        self.client.session_key = session_key or None

    def begin_login(self) -> Tuple[str, str]:
        """A fresh (token, approval URL) for the browser login."""
        token = self.client.get_token()
        return token, self.client.auth_url(token)

    def complete_login(self, token: str) -> Tuple[str, str]:
        """(user name, session key); raises TOKEN_NOT_AUTHORIZED until the user approves."""
        return self.client.get_session(token)

    def now_playing(self, path: Path, duration_s: int) -> str:
        """Failed now-playing updates are not retried; returns an error message or ""."""
        if not self.logged_in:
            return ""
        entry = self.read_tags(path, 0, duration_s)
        if entry is None:
            return ""
        try:
            self.client.update_now_playing(entry)
        except LastfmError as error:
            return error.message
        return ""

    def add(self, path: Path, started_at: int, duration_s: int) -> bool:
        """Queue a finished play; False when the file lacks the tags Last.fm needs."""
        entry = self.read_tags(path, started_at, duration_s)
        if entry is None:
            return False
        self.pending.append(entry)
        del self.pending[:-MAX_PENDING]
        self._save()
        return True

    def flush(self) -> FlushResult:
        result = FlushResult()
        if not self.pending or not self.logged_in:
            return result
        for batch in chunks(list(self.pending)):
            try:
                self.client.scrobble(batch)
            except LastfmError as error:
                result.error = error.message
                if error.session_invalid:
                    self.client.session_key = None
                    result.session_lost = True
                    break
                if error.retryable:
                    result.retry_later = True
                    break
                # Anything else means the batch itself is malformed; resending cannot help.
                result.dropped += len(batch)
            else:
                result.sent += len(batch)
            del self.pending[: len(batch)]
            self._save()
        return result

    def _load(self):
        if self.queue_path is None or not self.queue_path.exists():
            return
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
            self.pending = [Scrobble.from_dict(entry) for entry in data]
        except (OSError, ValueError, KeyError, TypeError):
            self.pending = []

    def _save(self):
        if self.queue_path is None:
            return
        tmp = self.queue_path.with_name(self.queue_path.name + ".tmp")
        tmp.write_text(json.dumps([entry.to_dict() for entry in self.pending]), encoding="utf-8")
        tmp.replace(self.queue_path)
