import json

import pytest
from PySide6.QtTest import QTest

from tag_gui.core.settings import Settings
from tag_gui.ui import lastfm as lastfm_module
from tag_gui.ui.dialogs import SettingsDialog
from tag_gui.ui.lastfm import LastfmController

from test_lastfm import KEY, SECRET, FakeLastfm


def wait_until(condition, timeout_ms=5000):
    for _ in range(timeout_ms // 20):
        if condition():
            return True
        QTest.qWait(20)
    return condition()


@pytest.fixture
def opened_urls(monkeypatch):
    urls = []
    monkeypatch.setattr(lastfm_module.QDesktopServices, "openUrl", lambda url: urls.append(url))
    monkeypatch.setattr(lastfm_module, "LOGIN_POLL_SECONDS", 0.05)
    return urls


@pytest.fixture
def server():
    return FakeLastfm()


@pytest.fixture
def make_controller(qapp, tmp_path, server):
    controllers = []

    def make():
        controller = LastfmController(tmp_path, credentials=(KEY, SECRET), post=server.post)
        controllers.append(controller)
        return controller

    yield make
    for controller in controllers:
        controller.shutdown()


def test_without_api_keys_scrobbling_is_unavailable(qapp, tmp_path):
    controller = LastfmController(tmp_path, credentials=())
    assert not controller.available
    controller.track_started("song.flac")
    controller.tick()
    dialog = SettingsDialog(Settings(), lastfm=controller)
    assert "Not available" in dialog.lastfm_box.status.text()
    assert dialog.lastfm_box.connect_button.isHidden()


def test_connect_opens_the_browser_and_stores_only_the_session(
    make_controller, server, opened_urls, tmp_path
):
    controller = make_controller()
    dialog_results = []
    controller.login_finished.connect(lambda ok, message: dialog_results.append(ok))
    controller.connect_account()
    assert wait_until(lambda: opened_urls)
    assert "token=tok123" in opened_urls[0].toString()
    assert not controller.connected

    server.approved = True
    assert wait_until(lambda: controller.connected)
    assert controller.username == "juha"
    assert dialog_results == [True]
    saved = json.loads((tmp_path / "lastfm.json").read_text())
    assert saved == {"username": "juha", "session_key": "sk-1"}

    # A restart picks the session up again without logging in.
    again = make_controller()
    assert again.connected and again.username == "juha"

    controller.disconnect_account()
    assert not controller.connected and not (tmp_path / "lastfm.json").exists()


def test_cancelled_login_stops_polling(make_controller, server, opened_urls):
    controller = make_controller()
    controller.connect_account()
    assert wait_until(lambda: opened_urls)
    controller.cancel_login()
    QTest.qWait(200)
    polls = [call["method"] for call in server.calls].count("auth.getSession")
    server.approved = True
    QTest.qWait(300)
    assert [call["method"] for call in server.calls].count("auth.getSession") == polls
    assert not controller.connected


def test_a_counted_play_is_scrobbled(make_controller, server, tmp_path, monkeypatch):
    (tmp_path / "lastfm.json").write_text(json.dumps({"username": "juha", "session_key": "sk-1"}))
    from tag_gui.core import scrobbling
    from tag_gui.core.lastfm import Scrobble

    monkeypatch.setattr(
        scrobbling,
        "read_scrobble_tags",
        lambda path, started_at, duration_s: Scrobble("Kaija", path.stem, started_at),
    )
    controller = make_controller()
    clock = [0.0]
    controller.tracker._clock = lambda: clock[0]

    controller.track_started(str(tmp_path / "talvi.flac"))
    controller.set_duration(100_000)
    assert wait_until(
        lambda: any(c["method"] == "track.updateNowPlaying" for c in server.calls)
    )
    clock[0] = 49
    controller.tick()
    clock[0] = 51
    controller.tick()
    controller.tick()
    assert wait_until(lambda: any(c["method"] == "track.scrobble" for c in server.calls))
    QTest.qWait(100)
    scrobbles = [c for c in server.calls if c["method"] == "track.scrobble"]
    assert len(scrobbles) == 1 and scrobbles[0]["track[0]"] == "talvi"


def test_settings_dialog_shows_the_connected_account(make_controller, tmp_path):
    (tmp_path / "lastfm.json").write_text(json.dumps({"username": "juha", "session_key": "sk-1"}))
    controller = make_controller()
    dialog = SettingsDialog(Settings(), lastfm=controller)
    box = dialog.lastfm_box
    assert "juha" in box.status.text()
    assert not box.disconnect_button.isHidden() and box.connect_button.isHidden()

    box.disconnect_button.click()
    assert "Not connected" in box.status.text()
    assert not box.connect_button.isHidden()
