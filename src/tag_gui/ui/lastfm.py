"""Last.fm scrobbling for the window: play tracking, a network thread and the login state."""

import json
import queue
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from ..core.lastfm import (
    NETWORK_ERROR,
    TOKEN_NOT_AUTHORIZED,
    LastfmClient,
    LastfmError,
    load_api_credentials,
)
from ..core.listening import ListenTracker
from ..core.scrobbling import ScrobbleService

# How long to wait before resending after Last.fm was offline or unreachable.
RETRY_SECONDS = 300
# While waiting for the user to click "Allow" on last.fm.
LOGIN_POLL_SECONDS = 3
LOGIN_TIMEOUT_SECONDS = 600
STOP_WAIT_SECONDS = 2


class ScrobbleWorker(QObject):
    """Runs every Last.fm call on one background thread, so the UI never waits on the network.

    Methods are called from the UI thread and only queue jobs; results come back as signals,
    which Qt delivers on the UI thread.
    """

    login_url = Signal(str)
    login_finished = Signal(bool, str, str, str)  # ok, user name, session key, message
    session_lost = Signal()

    def __init__(self, service: ScrobbleService, parent=None, clock=time.monotonic):
        super().__init__(parent)
        self._service = service
        self._clock = clock
        self._jobs: "queue.Queue[tuple]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="lastfm", daemon=True)
        self._retry_at: Optional[float] = None
        self._token: Optional[str] = None
        self._token_deadline = 0.0

    def start(self):
        self._thread.start()

    def stop(self):
        self._jobs.put(("stop",))
        # A request can hang until its timeout; unsent plays are already on disk.
        self._thread.join(STOP_WAIT_SECONDS)

    def set_session(self, session_key: Optional[str]):
        self._jobs.put(("session", session_key))

    def begin_login(self):
        self._jobs.put(("begin_login",))

    def cancel_login(self):
        self._jobs.put(("cancel_login",))

    def now_playing(self, path: str, duration_s: int):
        self._jobs.put(("now_playing", path, duration_s))

    def scrobble(self, path: str, started_at: int, duration_s: int):
        self._jobs.put(("scrobble", path, started_at, duration_s))

    def flush(self):
        self._jobs.put(("flush",))

    def _wait_seconds(self) -> Optional[float]:
        waits = []
        if self._token is not None:
            waits.append(LOGIN_POLL_SECONDS)
        if self._retry_at is not None:
            waits.append(max(0.0, self._retry_at - self._clock()))
        return min(waits) if waits else None

    def _run(self):
        while True:
            try:
                job = self._jobs.get(timeout=self._wait_seconds())
            except queue.Empty:
                job = ("timer",)
            if job[0] == "stop":
                return
            try:
                self._handle(job[0], job[1:])
            except Exception:  # noqa: BLE001 - one bad job must not end scrobbling
                continue

    def _handle(self, kind: str, args: tuple):
        service = self._service
        if kind == "timer":
            if self._token is not None:
                self._poll_login()
            if self._retry_at is not None and self._clock() >= self._retry_at:
                self._flush()
        elif kind == "session":
            service.set_session(args[0])
            self._flush()
        elif kind == "begin_login":
            try:
                token, url = service.begin_login()
            except LastfmError as error:
                self.login_finished.emit(False, "", "", error.message)
                return
            self._token = token
            self._token_deadline = self._clock() + LOGIN_TIMEOUT_SECONDS
            self.login_url.emit(url)
        elif kind == "cancel_login":
            self._token = None
        elif kind == "now_playing":
            service.now_playing(Path(args[0]), args[1])
        elif kind == "scrobble":
            path, started_at, duration_s = args
            if service.logged_in and service.add(Path(path), started_at, duration_s):
                self._flush()
        elif kind == "flush":
            self._flush()

    def _poll_login(self):
        token = self._token
        try:
            name, key = self._service.complete_login(token)
        except LastfmError as error:
            if error.code in (TOKEN_NOT_AUTHORIZED, NETWORK_ERROR) and (
                self._clock() < self._token_deadline
            ):
                return  # not approved yet, or a network blip: keep waiting
            self._token = None
            message = "Approval timed out" if error.code == TOKEN_NOT_AUTHORIZED else error.message
            self.login_finished.emit(False, "", "", message)
            return
        self._token = None
        self.login_finished.emit(True, name, key, "")
        self._flush()

    def _flush(self):
        result = self._service.flush()
        self._retry_at = self._clock() + RETRY_SECONDS if result.retry_later else None
        if result.session_lost:
            self.session_lost.emit()


class LastfmController(QObject):
    """The window's handle on scrobbling: account state plus hooks for the player."""

    login_waiting = Signal(str)  # approval URL, already opened in the browser
    login_finished = Signal(bool, str)  # ok, error message
    account_changed = Signal()
    session_lost = Signal()

    def __init__(self, data_dir: Path, parent=None, credentials=None, post=None):
        super().__init__(parent)
        self._account_file = data_dir / "lastfm.json"
        self.username: Optional[str] = None
        self.tracker = ListenTracker()
        self._worker: Optional[ScrobbleWorker] = None

        credentials = credentials if credentials is not None else load_api_credentials()
        if not credentials:
            return
        api_key, secret = credentials
        client = LastfmClient(api_key, secret, post=post) if post else LastfmClient(api_key, secret)
        service = ScrobbleService(client, data_dir / "scrobble_queue.json")
        self._worker = ScrobbleWorker(service, self)
        self._worker.login_url.connect(self._on_login_url)
        self._worker.login_finished.connect(self._on_login_finished)
        self._worker.session_lost.connect(self._on_session_lost)
        self._worker.start()

        session_key = self._load_account()
        if session_key:
            self._worker.set_session(session_key)

    @property
    def available(self) -> bool:
        return self._worker is not None

    @property
    def connected(self) -> bool:
        return self.username is not None

    # ------------------------------------------------------------- account

    def connect_account(self):
        """Start the browser login: last.fm opens, and the user clicks "Allow" there."""
        if self._worker is not None:
            self._worker.begin_login()

    def cancel_login(self):
        if self._worker is not None:
            self._worker.cancel_login()

    def _on_login_url(self, url: str):
        QDesktopServices.openUrl(QUrl(url))
        self.login_waiting.emit(url)

    def disconnect_account(self):
        self.username = None
        self._account_file.unlink(missing_ok=True)
        if self._worker is not None:
            self._worker.set_session(None)
        self.account_changed.emit()

    def _on_login_finished(self, ok: bool, name: str, key: str, message: str):
        if ok:
            self.username = name
            self._save_account(name, key)
            self.account_changed.emit()
        self.login_finished.emit(ok, message)

    def _on_session_lost(self):
        # The user revoked the app on last.fm; plays wait in the queue until they log in again.
        self.username = None
        self._account_file.unlink(missing_ok=True)
        self.account_changed.emit()
        self.session_lost.emit()

    def _load_account(self) -> Optional[str]:
        try:
            data = json.loads(self._account_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        name, key = data.get("username"), data.get("session_key")
        if isinstance(name, str) and isinstance(key, str) and name and key:
            self.username = name
            return key
        return None

    def _save_account(self, name: str, key: str):
        # The session key is all the app ever holds; the password stays on last.fm.
        self._account_file.write_text(
            json.dumps({"username": name, "session_key": key}), encoding="utf-8"
        )

    # ---------------------------------------------------------- playback hooks

    def track_started(self, path: str):
        self.tick()
        self.tracker.start(path, int(time.time()))
        self.tracker.resume()
        if self._worker is not None and self.connected:
            self._worker.now_playing(path, 0)

    def set_duration(self, duration_ms: int):
        self.tracker.set_duration(duration_ms)

    def set_playing(self, playing: bool):
        if playing:
            self.tracker.resume()
        else:
            self.tick()
            self.tracker.pause()

    def tick(self):
        """Called as playback advances; queues the play once it counts as a scrobble."""
        if self._worker is None or not self.connected:
            return
        if self.tracker.take_scrobble():
            self._worker.scrobble(
                self.tracker.track, self.tracker.started_at, self.tracker.duration_ms // 1000
            )

    def shutdown(self):
        if self._worker is not None:
            self._worker.stop()
            self._worker = None
