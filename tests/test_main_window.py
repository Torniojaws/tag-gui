"""One offscreen run of the real window, so a broken mixin or layout fails the suite."""

import pytest

from tag_gui.constants import DEFAULT_COLUMNS
from tag_gui.ui import main_window as main_window_module
from tag_gui.ui.main_window import MainWindow

from conftest import write_flac


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
    for name in ("tags_input", "tabs", "transport", "volume", "progress", "player"):
        assert getattr(window, name) is not None
    assert window.centralWidget() is not None


def test_adding_a_track_fills_a_row(window, tmp_path, monkeypatch):
    song = write_flac(tmp_path / "song.flac")
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist([str(song)])

    table = window.current_table()
    assert table.rowCount() == 1
    assert table.columnCount() == len(DEFAULT_COLUMNS)
    assert window.current_playlist().tracks == [str(song)]


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
