import hashlib
import json
import urllib.parse

import pytest

from tag_gui.core.lastfm import (
    AUTH_URL,
    INVALID_SESSION,
    NETWORK_ERROR,
    TOKEN_NOT_AUTHORIZED,
    LastfmClient,
    LastfmError,
    Scrobble,
    sign,
)
from tag_gui.core.listening import ListenTracker, needed_ms
from tag_gui.core.scrobbling import ScrobbleService, read_scrobble_tags

KEY = "testkey"
SECRET = "testsecret"


class FakeLastfm:
    """Answers like ws.audioscrobbler.com and checks every request signature."""

    def __init__(self):
        self.calls = []
        self.approved = False
        self.scrobble_error = None
        self.offline = False

    def post(self, url, body):
        if self.offline:
            raise OSError("network is unreachable")
        params = {k: v[0] for k, v in urllib.parse.parse_qs(body.decode("utf-8")).items()}
        signed = {k: v for k, v in params.items() if k not in ("api_sig", "format")}
        assert params["api_sig"] == sign(signed, SECRET)
        assert params["format"] == "json"
        assert params["api_key"] == KEY
        self.calls.append(params)
        method = params["method"]
        if method == "auth.getToken":
            return self._ok({"token": "tok123"})
        if method == "auth.getSession":
            if not self.approved:
                return self._error(TOKEN_NOT_AUTHORIZED, "This token has not been authorized")
            return self._ok({"session": {"name": "juha", "key": "sk-1", "subscriber": 0}})
        if params.get("sk") != "sk-1":
            return self._error(INVALID_SESSION, "Invalid session key")
        if method == "track.updateNowPlaying":
            return self._ok({"nowplaying": {}})
        if method == "track.scrobble":
            if self.scrobble_error:
                return self._error(*self.scrobble_error)
            count = sum(1 for name in params if name.startswith("artist["))
            return self._ok({"scrobbles": {"@attr": {"accepted": count, "ignored": 0}}})
        return self._error(3, "Invalid method")

    @staticmethod
    def _ok(data):
        return json.dumps(data).encode("utf-8")

    @staticmethod
    def _error(code, message):
        return json.dumps({"error": code, "message": message}).encode("utf-8")


@pytest.fixture
def server():
    return FakeLastfm()


@pytest.fixture
def client(server):
    return LastfmClient(KEY, SECRET, post=server.post)


def test_signature_is_md5_of_sorted_params_and_secret():
    params = {"method": "auth.getToken", "api_key": "K", "format": "json"}
    expected = hashlib.md5(b"api_keyKmethodauth.getTokenS").hexdigest()
    assert sign(params, "S") == expected


def test_browser_login_flow(client, server):
    token = client.get_token()
    assert token == "tok123"
    url = client.auth_url(token)
    assert url.startswith(AUTH_URL)
    assert dict(urllib.parse.parse_qsl(url.split("?", 1)[1])) == {"api_key": KEY, "token": token}

    with pytest.raises(LastfmError) as waiting:
        client.get_session(token)
    assert waiting.value.code == TOKEN_NOT_AUTHORIZED

    server.approved = True
    assert client.get_session(token) == ("juha", "sk-1")
    assert client.session_key == "sk-1"


def test_scrobble_batch_sends_indexed_tracks(client, server):
    client.session_key = "sk-1"
    entries = [
        Scrobble("Artist A", "Song A", 1_700_000_000, album="Album", duration=200, track_number=3),
        Scrobble("Artist B", "Song B", 1_700_000_300),
    ]
    assert client.scrobble(entries) == 2
    sent = server.calls[-1]
    assert sent["artist[0]"] == "Artist A" and sent["trackNumber[0]"] == "3"
    assert sent["track[1]"] == "Song B" and sent["timestamp[1]"] == "1700000300"
    assert "album[1]" not in sent


def test_errors_are_classified(client, server):
    with pytest.raises(LastfmError) as no_session:
        client.update_now_playing(Scrobble("A", "B", 0))
    assert no_session.value.session_invalid

    server.offline = True
    client.session_key = "sk-1"
    with pytest.raises(LastfmError) as offline:
        client.scrobble([Scrobble("A", "B", 1)])
    assert offline.value.code == NETWORK_ERROR and offline.value.retryable


# ------------------------------------------------------------- play counting


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_needed_time_follows_the_last_fm_rule():
    assert needed_ms(30_000) is None
    assert needed_ms(60_000) == 30_000
    assert needed_ms(20 * 60_000) == 240_000


def test_tracker_counts_only_time_spent_playing():
    clock = FakeClock()
    tracker = ListenTracker(clock)
    tracker.start("song.flac", 1_700_000_000)
    tracker.set_duration(100_000)
    tracker.resume()
    clock.now = 30
    tracker.pause()
    clock.now = 500  # paused for a long time
    assert not tracker.take_scrobble()
    tracker.resume()
    clock.now = 519
    assert not tracker.take_scrobble()
    clock.now = 521
    assert tracker.take_scrobble()
    assert not tracker.take_scrobble()  # only once per play

    tracker.start("song.flac", 1_700_000_600)
    assert not tracker.take_scrobble()


def test_short_tracks_never_count():
    clock = FakeClock()
    tracker = ListenTracker(clock)
    tracker.start("jingle.mp3", 0)
    tracker.set_duration(25_000)
    tracker.resume()
    clock.now = 25
    assert not tracker.take_scrobble()


# ------------------------------------------------------------ the service


def fake_tags(path, started_at, duration_s):
    if "untagged" in path.name:
        return None
    return Scrobble("Artist", path.stem, started_at, duration=duration_s)


@pytest.fixture
def service(client, tmp_path):
    client.session_key = "sk-1"
    return ScrobbleService(client, tmp_path / "queue.json", read_tags=fake_tags)


def test_plays_are_sent_and_untagged_files_skipped(service, server, tmp_path):
    assert service.add(tmp_path / "one.flac", 100, 200)
    assert not service.add(tmp_path / "untagged.flac", 200, 200)
    result = service.flush()
    assert result.sent == 1 and service.pending == []
    assert server.calls[-1]["track[0]"] == "one"


def test_unsent_plays_survive_offline_and_restarts(service, server, client, tmp_path):
    server.offline = True
    service.add(tmp_path / "one.flac", 100, 200)
    result = service.flush()
    assert result.retry_later and len(service.pending) == 1

    reloaded = ScrobbleService(client, tmp_path / "queue.json", read_tags=fake_tags)
    assert [entry.track for entry in reloaded.pending] == ["one"]
    server.offline = False
    assert reloaded.flush().sent == 1
    assert ScrobbleService(client, tmp_path / "queue.json").pending == []


def test_lost_session_keeps_plays_and_bad_batches_are_dropped(service, server, client, tmp_path):
    service.add(tmp_path / "one.flac", 100, 200)
    client.session_key = "revoked"
    result = service.flush()
    assert result.session_lost and not service.logged_in and len(service.pending) == 1

    client.session_key = "sk-1"
    server.scrobble_error = (6, "Invalid parameters")
    result = service.flush()
    assert result.dropped == 1 and service.pending == []


def test_large_backlogs_go_out_in_batches_of_50(service, server, tmp_path):
    for index in range(120):
        service.pending.append(Scrobble("A", f"Song {index}", index))
    assert service.flush().sent == 120
    assert [call["method"] for call in server.calls].count("track.scrobble") == 3


def test_real_tags_are_required(tmp_path):
    from conftest import write_flac
    from tag_gui.core.tags import set_standard_tags

    song = write_flac(tmp_path / "song.flac")
    assert read_scrobble_tags(song, 1, 3) is None
    set_standard_tags(song, {"artist": "Kaija", "title": "Talvi", "tracknumber": "4/9"})
    entry = read_scrobble_tags(song, 1, 3)
    assert (entry.artist, entry.track, entry.track_number, entry.duration) == ("Kaija", "Talvi", 4, 3)
