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


def test_home_and_end_scroll_the_playlist(window, tmp_path, monkeypatch):
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(60)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    window.resize(800, 400)
    window.show()
    table = window.current_table()
    table.selectRow(5)
    bar = table.verticalScrollBar()
    assert bar.maximum() > 0

    QTest.keyClick(table, Qt.Key_End)
    assert bar.value() == bar.maximum()
    QTest.keyClick(table, Qt.Key_Home)
    assert bar.value() == bar.minimum()
    assert [i.row() for i in table.selectionModel().selectedRows()] == [5]


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


def tagged_songs(tmp_path, rows):
    from tag_gui.core.tags import set_standard_tags

    songs = []
    for index, (artist, title, album, year) in enumerate(rows):
        song = write_flac(tmp_path / f"tagged{index}.flac")
        set_standard_tags(song, {"artist": artist, "title": title, "album": album, "date": year})
        songs.append(str(song))
    return songs


@pytest.fixture
def filtered_window(window, tmp_path, monkeypatch):
    songs = tagged_songs(
        tmp_path,
        [
            ("Iron Maiden", "Aces High", "Powerslave", "1984"),
            ("Metallica", "One", "...And Justice for All", "1988"),
            ("Maiden Voyage", "Iron Man", "Iron", "1999"),
            ("Slayer", "Angel of Death", "Reign in Blood", "1986"),
        ],
    )
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    window.show()
    window.activateWindow()
    QTest.qWaitForWindowActive(window)
    return window


def visible_artists(window):
    table = window.current_table()
    return [
        table.item(row, 0).text() for row in range(table.rowCount()) if not table.isRowHidden(row)
    ]


def test_ctrl_f_toggles_the_search_bar(filtered_window):
    window = filtered_window
    assert window.search_row.isHidden()
    QTest.keyClick(window, Qt.Key_F, Qt.ControlModifier)
    assert not window.search_row.isHidden()
    assert window.search_input.hasFocus()

    QTest.keyClicks(window.search_input, "maiden")
    assert len(visible_artists(window)) == 2

    QTest.keyClick(window.search_input, Qt.Key_F, Qt.ControlModifier)
    assert window.search_row.isHidden()
    assert window.search_input.text() == ""
    assert len(visible_artists(window)) == 4


def test_search_matches_artist_song_or_album_once(filtered_window):
    window = filtered_window
    window.open_search()

    window.search_input.setText("IRON")
    # Matches artist, then title and album of the same row, which is listed once.
    assert visible_artists(window) == ["Iron Maiden", "Maiden Voyage"]
    assert window.search_count.text() == "2 of 4"

    window.search_input.setText("justice")
    assert visible_artists(window) == ["Metallica"]
    window.search_input.setText("angel of")
    assert visible_artists(window) == ["Slayer"]
    window.search_input.setText("1984")
    assert visible_artists(window) == []

    window.search_input.clear()
    assert len(visible_artists(window)) == 4
    assert window.search_count.text() == ""


def test_hidden_rows_are_left_out_of_selection_and_playback(filtered_window, monkeypatch):
    from tag_gui.ui.table_fill import selected_tracks

    window = filtered_window
    monkeypatch.setattr(window.player, "play", lambda: None)
    window.open_search()
    window.search_input.setText("maiden")
    table = window.current_table()
    table.selectAll()
    assert len(selected_tracks(table)) == 2

    visible = [row for row in range(table.rowCount()) if not table.isRowHidden(row)]
    window.play_next()
    assert window.current_track_index == visible[0]
    window.play_next()
    assert window.current_track_index == visible[1]
    window.play_next()
    assert window.current_track_index == visible[0]
    window.play_previous()
    assert window.current_track_index == visible[1]


def test_filter_survives_sorting_and_tab_switches(filtered_window):
    window = filtered_window
    window.open_search()
    window.search_input.setText("maiden")
    table = window.current_table()
    table.sort_by_column(0)
    assert sorted(visible_artists(window)) == ["Iron Maiden", "Maiden Voyage"]

    window.add_playlist()
    assert window.search_count.text() == "0 of 0"
    window.tabs.setCurrentIndex(0)
    assert sorted(visible_artists(window)) == ["Iron Maiden", "Maiden Voyage"]


def wait_until(condition, timeout_ms=5000):
    for _ in range(timeout_ms // 20):
        if condition():
            return True
        QTest.qWait(20)
    return condition()


def year_tagged_songs(tmp_path):
    from tag_gui.core.tags import set_standard_tags

    songs = []
    for name, year, number in (("c", "2001", "1"), ("a", "1990", "2"), ("b", "1990", "1")):
        song = write_flac(tmp_path / f"{name}.flac")
        set_standard_tags(song, {"album": f"Album {year}", "date": year, "tracknumber": number})
        songs.append(str(song))
    return songs


def test_sort_dropdown_reorders_only_the_current_playlist(window, tmp_path, monkeypatch):
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    songs = year_tagged_songs(tmp_path)
    window.add_tracks_to_current_playlist(songs)
    window.add_playlist()
    window.add_tracks_to_current_playlist(list(songs))
    window.tabs.setCurrentIndex(0)
    table = window.current_table()
    table.sort_by_column(0)

    combo = window.sort_combo
    combo.activated.emit(combo.findData("oldest"))
    assert combo.currentIndex() == -1
    assert wait_until(lambda: not window.is_sorting())

    expected = [songs[2], songs[1], songs[0]]
    assert window.current_playlist().tracks == expected
    assert [table.item(row, 0).data(Qt.UserRole) for row in range(3)] == expected
    assert window.playlists[1].tracks == songs
    assert combo.isEnabled()
    assert window.sort_status.text().endswith("Sorting completed")
    assert window.sort_note.isVisibleTo(window)
    assert not window.sort_spinner.is_spinning()

    window._sort_done_timer.setInterval(10)
    window._sort_done_fade.setDuration(10)
    window.show_sort_done()
    assert wait_until(lambda: window.sort_note.isHidden(), 2000)

    combo.activated.emit(combo.findData("path"))
    assert window.current_playlist().tracks == sorted(songs)


def test_year_sort_reads_track_numbers_off_the_ui_thread(window, tmp_path, monkeypatch):
    import threading

    from tag_gui.ui import sorting

    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    songs = year_tagged_songs(tmp_path)
    window.add_tracks_to_current_playlist(songs)
    for track in songs:
        window.metadata.get(track, []).position = None
    release = threading.Event()
    reader_threads = []
    real_read = sorting.read_track_position

    def slow_read(path):
        reader_threads.append(threading.current_thread())
        release.wait(5)
        return real_read(path)

    monkeypatch.setattr(sorting, "read_track_position", slow_read)
    window.sort_current_playlist("newest")

    # The UI keeps running while the worker is blocked on a file read.
    assert wait_until(lambda: window.sort_spinner.is_spinning(), 2000)
    assert not window.sort_combo.isEnabled()
    window.add_playlist()
    window.tabs.setCurrentIndex(0)
    release.set()
    assert wait_until(lambda: not window.is_sorting())

    assert threading.main_thread() not in reader_threads
    assert window.playlists[0].tracks == [songs[0], songs[2], songs[1]]
    assert window.metadata.cached_position(songs[1]) == (0, 2)


def test_closing_the_window_stops_a_running_sort(window, tmp_path, monkeypatch):
    import threading

    from tag_gui.ui import sorting

    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    songs = year_tagged_songs(tmp_path)
    window.add_tracks_to_current_playlist(songs)
    for track in songs:
        window.metadata.get(track, []).position = None
    started = threading.Event()

    def slow_read(path):
        started.set()
        QTest.qWait(50)
        return (0, 0)

    monkeypatch.setattr(sorting, "read_track_position", slow_read)
    window.sort_current_playlist("oldest")
    assert started.wait(2)
    window.close()
    assert not window.is_sorting()
    assert window.playlists[0].tracks == songs


def test_album_shading_is_painted_per_album_run(qapp):
    from PySide6.QtWidgets import QTableWidgetItem

    from tag_gui.constants import ALBUM_COLUMN
    from tag_gui.ui.table import PlaylistTable

    table = PlaylistTable(None, None, None, None)
    table.setColumnCount(len(DEFAULT_COLUMNS))
    table.setRowCount(3)
    for row, album in enumerate(("A", "A", "B")):
        table.setItem(row, ALBUM_COLUMN, QTableWidgetItem(album))
        table.setItem(row, 0, QTableWidgetItem(""))
    table.resize(600, 200)
    table.apply_album_colors()
    image = table.viewport().grab().toImage()

    def color(row):
        rect = table.visualRect(table.model().index(row, 0))
        return image.pixelColor(rect.left() + 3, rect.center().y()).name()

    assert color(0) == color(1)
    assert color(0) != color(2)
    table.reorder([])  # nothing known: rows keep their order
    assert [table.item(row, ALBUM_COLUMN).text() for row in range(3)] == ["A", "A", "B"]


def test_shuffle_checkbox_sits_right_of_next_and_is_remembered(window):
    from tag_gui.core.settings import load_settings

    transport = window.transport
    layout = transport.layout()
    widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
    widgets = [w for w in widgets if w is not None]
    assert widgets.index(transport.shuffle_box) == widgets.index(transport.next_btn) + 1

    transport.shuffle_box.setChecked(True)
    assert window.settings.shuffle
    assert load_settings(window.settings_file).shuffle

    # Saving the Settings dialog must not switch shuffle back off.
    assert SettingsDialog(window.settings).settings().shuffle


def test_shuffle_avoids_recent_artists_and_previous_walks_back(window, tmp_path, monkeypatch):
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    monkeypatch.setattr(window.player, "play", lambda: None)
    rows = [("Metallica", f"Song {i}", "Black", "1991") for i in range(4)]
    rows += [("Slayer", "Angel of Death", "Reign", "1986"), ("Bathory", "Odens Ride", "Blood", "1988")]
    songs = tagged_songs(tmp_path, rows)
    window.add_tracks_to_current_playlist(songs)
    window.transport.shuffle_box.setChecked(True)
    table = window.current_table()

    def playing():
        return table.item(window.current_track_index, 0).data(Qt.UserRole)

    window.play_row(0)
    played = [playing()]
    for _ in range(2):
        window.play_next()
        played.append(playing())
    artists = [window.metadata.get(t, []).fields[0] for t in played]
    # Two non-Metallica tracks exist, so the first three picks never repeat an artist.
    assert len(set(artists)) == 3

    window.play_previous()
    assert playing() == played[1]
    window.play_previous()
    assert playing() == played[0]
