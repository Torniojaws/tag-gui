"""One offscreen run of the real window, so a broken mixin or layout fails the suite."""

import pytest
from PySide6.QtCore import QEvent, QItemSelectionModel, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from tag_gui.constants import DEFAULT_COLUMNS
from tag_gui.core.settings import Settings
from tag_gui.ui import main_window as main_window_module
from tag_gui.ui.dialogs import SettingsDialog, SkipSecondsInput
from tag_gui.ui.main_window import MainWindow

from conftest import write_flac


class FakePlayer:
    def __init__(self, position, duration):
        self._position = position
        self._duration = duration

    def position(self):
        return self._position

    def duration(self):
        return self._duration

    def setPosition(self, position):
        self._position = position

    def playbackState(self):
        return QMediaPlayer.PlayingState


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(main_window_module, "app_data_dir", lambda: tmp_path)
    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()


def test_a_fresh_window_opens_one_default_playlist(window):
    assert window.tabs.count() == 1
    assert [p.name for p in window.playlists] == ["default"]
    assert window.current_table() is window.tabs.widget(0)


def test_every_slice_contributed_its_widgets(window):
    for name in ("tags_input", "tabs", "transport", "volume", "player"):
        assert getattr(window, name) is not None
    assert window.progress_top.isHidden()
    assert not window.progress_bottom.isHidden()
    assert window.centralWidget() is not None


def test_adding_a_track_fills_a_row(window, tmp_path, monkeypatch):
    song = write_flac(tmp_path / "song.flac")
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist([str(song)])

    table = window.current_table()
    assert table.rowCount() == 1
    assert table.columnCount() == len(DEFAULT_COLUMNS)
    assert window.current_playlist().tracks == [str(song)]


def test_copy_paste_moves_selected_tracks_to_another_playlist(window, tmp_path, monkeypatch):
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(3)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    source = window.current_table()
    source.selectRow(0)
    source.selectionModel().select(
        source.model().index(2, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    window.copy_selected_tracks()

    window.add_playlist()
    window.paste_tracks()
    window.paste_tracks()

    assert window.current_playlist().tracks == [songs[0], songs[2]]
    assert window.current_table().rowCount() == 2


def test_copy_files_to_dir_copies_the_playlist(window, tmp_path, monkeypatch):
    from tag_gui.ui import file_actions

    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(2)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    target = tmp_path / "usb"
    monkeypatch.setattr(
        file_actions.QFileDialog, "getExistingDirectory", lambda *args: str(target)
    )
    messages = []
    monkeypatch.setattr(
        file_actions.QMessageBox, "information", lambda *args: messages.append(args[2])
    )

    window.copy_playlist_to_dir()

    assert sorted(p.name for p in target.iterdir()) == ["song0.flac", "song1.flac"]
    assert all(tmp_path.joinpath(f"song{i}.flac").exists() for i in range(2))
    assert messages and messages[0].startswith("Copied 2 of 2 files")


def test_applying_custom_tags_adds_a_column(window):
    window.tags_input.setText("Yömusa, rock")
    window.apply_custom_tags()
    assert window.custom_tags == ["Yömusa", "rock"]
    assert window.current_table().columnCount() == len(DEFAULT_COLUMNS) + 2


def test_custom_tags_survive_a_restart(window, tmp_path, qapp, monkeypatch):
    window.tags_input.setText("rock")
    window.apply_custom_tags()
    window.close()

    monkeypatch.setattr(main_window_module, "app_data_dir", lambda: tmp_path)
    reopened = MainWindow()
    try:
        assert reopened.custom_tags == ["rock"]
    finally:
        reopened.close()
        reopened.deleteLater()


def arrow(key, repeat=False):
    return QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, "", repeat)


@pytest.fixture
def skipping(window, monkeypatch):
    """The window with a fake player 60 s long, recording every jump to the next song."""
    nexts = []
    monkeypatch.setattr(window, "player", FakePlayer(30_000, 60_000))
    monkeypatch.setattr(window, "play_next", lambda: nexts.append(True))
    monkeypatch.setattr(window, "isActiveWindow", lambda: True)
    window.settings = Settings(skip_seconds=5)
    window.nexts = nexts
    return window


def test_arrows_skip_by_the_configured_step(skipping):
    assert skipping._handle_skip_key(arrow(Qt.Key_Right))
    assert skipping.player.position() == 35_000
    skipping._handle_skip_key(arrow(Qt.Key_Left))
    skipping._handle_skip_key(arrow(Qt.Key_Left))
    assert skipping.player.position() == 25_000


def test_skipping_back_stops_at_the_start(skipping):
    skipping.player.setPosition(3_000)
    skipping._handle_skip_key(arrow(Qt.Key_Left))
    assert skipping.player.position() == 0
    skipping.player.setPosition(1_000)
    skipping._handle_skip_key(arrow(Qt.Key_Left, repeat=True))
    assert skipping.player.position() == 1_000


def test_holding_right_does_not_scrub_into_the_next_song(skipping):
    skipping.player.setPosition(57_000)
    skipping._handle_skip_key(arrow(Qt.Key_Right))
    assert skipping.nexts == [True]

    skipping.player.setPosition(0)
    assert skipping._handle_skip_key(arrow(Qt.Key_Right, repeat=True))
    assert skipping.player.position() == 0

    skipping._handle_skip_key(arrow(Qt.Key_Right))
    assert skipping.player.position() == 5_000


def test_arrows_are_left_alone_in_text_fields(skipping):
    skipping.show()
    skipping.tags_input.setFocus()
    QApplication.processEvents()
    if QApplication.focusWidget() is not skipping.tags_input:
        pytest.skip("focus is not tracked by this platform plugin")
    assert not skipping._handle_skip_key(arrow(Qt.Key_Right))
    assert skipping.player.position() == 30_000


def test_skip_seconds_input_keeps_only_digits(qapp):
    field = SkipSecondsInput(5)
    field.selectAll()
    QTest.keyClicks(field, "1asd6")
    assert (field.text(), field.value()) == ("16", 16)
    QTest.keyClicks(field, "9")
    assert field.value() == 16


def test_skip_seconds_input_falls_back_to_the_default(qapp):
    field = SkipSecondsInput(7)
    field.end(False)
    QTest.keyClick(field, Qt.Key_Backspace)
    assert (field.text(), field.value()) == ("5", 5)
    QTest.keyClicks(field, "9")
    assert field.value() == 9

    QApplication.clipboard().setText("abc")
    field.selectAll()
    field.paste()
    assert field.value() == 5


def test_settings_dialog_never_hides_both_timebars(qapp):
    dialog = SettingsDialog(Settings(timebar_top=False, timebar_bottom=True))
    assert not dialog.timebar_bottom.isEnabled()
    dialog.timebar_top.setChecked(True)
    assert dialog.timebar_bottom.isEnabled()
    dialog.timebar_bottom.setChecked(False)
    assert not dialog.timebar_top.isEnabled()
    assert dialog.settings() == Settings(timebar_top=True, timebar_bottom=False)


def test_timebar_settings_show_the_chosen_bars(window):
    window.settings = Settings(timebar_top=True, timebar_bottom=True)
    window.apply_settings()
    assert not window.progress_top.isHidden()
    assert not window.progress_bottom.isHidden()
