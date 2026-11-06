"""A small Last.fm API client: signing, desktop (browser) login, now playing and scrobbles.

Everything here is plain blocking I/O through an injectable ``post`` function, so the UI
runs it on a worker thread and the tests run it against a fake server.
"""

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

API_URL = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth/"
TIMEOUT_SECONDS = 15
MAX_BATCH = 50

# Error codes after which a scrobble should be sent again later, per the Last.fm docs.
RETRY_CODES = {11, 16}
INVALID_SESSION = 9
TOKEN_NOT_AUTHORIZED = 14
# Not a Last.fm code: the request never got an answer (offline, DNS, timeout).
NETWORK_ERROR = -1

Post = Callable[[str, bytes], bytes]


class LastfmError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"Last.fm error {code}: {message}")
        self.code = code
        self.message = message

    @property
    def retryable(self) -> bool:
        return self.code in RETRY_CODES or self.code == NETWORK_ERROR

    @property
    def session_invalid(self) -> bool:
        return self.code == INVALID_SESSION


@dataclass(frozen=True)
class Scrobble:
    artist: str
    track: str
    timestamp: int
    album: str = ""
    album_artist: str = ""
    duration: int = 0
    track_number: int = 0

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @classmethod
    def from_dict(cls, data: dict) -> "Scrobble":
        return cls(
            artist=str(data["artist"]),
            track=str(data["track"]),
            timestamp=int(data["timestamp"]),
            album=str(data.get("album", "")),
            album_artist=str(data.get("album_artist", "")),
            duration=int(data.get("duration", 0)),
            track_number=int(data.get("track_number", 0)),
        )


def sign(params: Dict[str, str], secret: str) -> str:
    """md5 of every parameter as <name><value> in name order, followed by the secret."""
    text = "".join(f"{name}{params[name]}" for name in sorted(params) if name != "format")
    return hashlib.md5((text + secret).encode("utf-8")).hexdigest()


def urllib_post(url: str, body: bytes) -> bytes:
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        # Last.fm puts the real error in the body, also for 4xx/5xx statuses.
        return error.read()


def _track_params(entry: Scrobble, suffix: str = "") -> Dict[str, str]:
    params = {f"artist{suffix}": entry.artist, f"track{suffix}": entry.track}
    if entry.album:
        params[f"album{suffix}"] = entry.album
    if entry.album_artist:
        params[f"albumArtist{suffix}"] = entry.album_artist
    if entry.duration:
        params[f"duration{suffix}"] = str(entry.duration)
    if entry.track_number:
        params[f"trackNumber{suffix}"] = str(entry.track_number)
    return params


class LastfmClient:
    def __init__(
        self,
        api_key: str,
        secret: str,
        session_key: Optional[str] = None,
        post: Post = urllib_post,
    ):
        self.api_key = api_key
        self.secret = secret
        self.session_key = session_key
        self._post = post

    def _call(self, method: str, params: Dict[str, str], with_session: bool = True) -> dict:
        params = dict(params, method=method, api_key=self.api_key)
        if with_session:
            if not self.session_key:
                raise LastfmError(INVALID_SESSION, "Not logged in")
            params["sk"] = self.session_key
        params["api_sig"] = sign(params, self.secret)
        params["format"] = "json"
        body = urllib.parse.urlencode(params).encode("utf-8")
        try:
            raw = self._post(API_URL, body)
        except (OSError, urllib.error.URLError) as error:
            raise LastfmError(NETWORK_ERROR, str(error)) from error
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as error:
            raise LastfmError(NETWORK_ERROR, "Unreadable response from Last.fm") from error
        if isinstance(data, dict) and "error" in data:
            raise LastfmError(int(data["error"]), str(data.get("message", "")))
        return data

    def get_token(self) -> str:
        """Step 1 of desktop login: a token the user approves on last.fm (valid 60 minutes)."""
        data = self._call("auth.getToken", {}, with_session=False)
        token = data.get("token")
        if not token:
            raise LastfmError(NETWORK_ERROR, "Last.fm returned no token")
        return str(token)

    def auth_url(self, token: str) -> str:
        """Step 2: the page where the user allows this app; the app never sees a password."""
        query = urllib.parse.urlencode({"api_key": self.api_key, "token": token})
        return f"{AUTH_URL}?{query}"

    def get_session(self, token: str) -> Tuple[str, str]:
        """Step 3: (user name, session key) once the token is approved. Raises
        TOKEN_NOT_AUTHORIZED until then. Session keys do not expire."""
        data = self._call("auth.getSession", {"token": token}, with_session=False)
        session = data.get("session") or {}
        name, key = session.get("name"), session.get("key")
        if not name or not key:
            raise LastfmError(NETWORK_ERROR, "Last.fm returned no session")
        self.session_key = key
        return name, key

    def update_now_playing(self, entry: Scrobble) -> None:
        self._call("track.updateNowPlaying", _track_params(entry))

    def scrobble(self, entries: Sequence[Scrobble]) -> int:
        """Send up to MAX_BATCH scrobbles; returns how many Last.fm accepted. Ignored ones
        (filtered by Last.fm, e.g. too old) are not errors and must not be resent."""
        if not 0 < len(entries) <= MAX_BATCH:
            raise ValueError(f"A batch holds 1 to {MAX_BATCH} scrobbles")
        params: Dict[str, str] = {}
        for index, entry in enumerate(entries):
            suffix = f"[{index}]"
            params.update(_track_params(entry, suffix))
            params[f"timestamp{suffix}"] = str(entry.timestamp)
        data = self._call("track.scrobble", params)
        attributes = (data.get("scrobbles") or {}).get("@attr") or {}
        return int(attributes.get("accepted", 0))


def load_api_credentials() -> Optional[Tuple[str, str]]:
    """The app's API key and secret, written into _lastfm_keys.py at build time.

    They are kept out of the repository, so a checkout without that file simply has no
    Last.fm support.
    """
    try:
        from .. import _lastfm_keys  # type: ignore[attr-defined]
    except ImportError:
        return None
    key = getattr(_lastfm_keys, "API_KEY", "")
    secret = getattr(_lastfm_keys, "API_SECRET", "")
    return (key, secret) if key and secret else None


def chunks(items: List[Scrobble], size: int = MAX_BATCH) -> List[List[Scrobble]]:
    return [items[start : start + size] for start in range(0, len(items), size)]
