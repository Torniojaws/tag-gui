"""One offscreen run of the real window, so a broken mixin or layout fails the suite."""

import pytest
from PySide6.QtCore import QEvent, QItemSelectionModel, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from tag_gui.constants import DEFAULT_COLUMNS, PATH_COLUMN
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


def test_mac_keys_remove_rows_and_scroll(window, tmp_path, monkeypatch):
    from tag_gui.ui import table as table_module

    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(60)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    window.resize(800, 400)
    window.show()
    table = window.current_table()
    bar = table.verticalScrollBar()

    # Elsewhere Backspace does nothing to the playlist.
    table.selectRow(0)
    QTest.keyClick(table, Qt.Key_Backspace)
    assert table.rowCount() == 60

    monkeypatch.setattr(table_module, "IS_MAC", True)
    table.selectRow(0)
    QTest.keyClick(table, Qt.Key_Backspace)
    assert table.rowCount() == 59
    table.selectRow(0)
    QTest.keyClick(table, Qt.Key_Backspace, Qt.ControlModifier)
    assert table.rowCount() == 58
    assert window.current_playlist().tracks == songs[2:]

    # Qt reports Cmd as Control on macOS, and arrows arrive with KeypadModifier.
    QTest.keyClick(table, Qt.Key_Down, Qt.ControlModifier | Qt.KeypadModifier)
    assert bar.value() == bar.maximum() > 0
    QTest.keyClick(table, Qt.Key_Up, Qt.ControlModifier | Qt.KeypadModifier)
    assert bar.value() == bar.minimum()
    QTest.keyClick(table, Qt.Key_End, Qt.KeypadModifier)
    assert bar.value() == bar.maximum()


def test_removing_tracks_keeps_the_table_and_scroll_position(window, tmp_path, monkeypatch):
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(60)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    window.resize(800, 400)
    window.show()
    table = window.current_table()
    bar = table.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    scroll = bar.value()
    kept_item = table.item(0, 0)

    def no_rebuild(*_args):
        raise AssertionError("removing tracks must not rebuild the table")

    monkeypatch.setattr(MainWindow, "populate_table", no_rebuild)
    table.selectRow(30)
    QTest.keyClick(table, Qt.Key_Delete)

    assert table.rowCount() == 59
    assert songs[30] not in window.current_playlist().tracks
    assert table.item(0, 0) is kept_item
    assert bar.value() == scroll
    paths = [table.item(row, PATH_COLUMN).data(Qt.UserRole) for row in range(59)]
    assert paths == songs[:30] + songs[31:]


def test_removing_a_track_keeps_the_search_filter(filtered_window):
    window = filtered_window
    window.open_search()
    window.search_input.setText("maiden")
    table = window.current_table()
    first_visible = next(row for row in range(table.rowCount()) if not table.isRowHidden(row))
    table.selectRow(first_visible)
    window.remove_selected_tracks()

    assert table.rowCount() == 3
    assert len(visible_artists(window)) == 1
    assert window.search_count.text() == "1 of 3"


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


def test_column_order_and_widths_are_shared_and_remembered(window, tmp_path, monkeypatch):
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(3)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    window.add_playlist()
    other = window.current_table()
    window.tabs.setCurrentIndex(0)
    first = window.current_table()
    # Filling tables sizes columns to fit, which must not count as the user's widths.
    assert window.settings.column_widths == {}

    header = first.horizontalHeader()
    header.moveSection(header.visualIndex(DEFAULT_COLUMNS.index("Song")), 0)
    header.resizeSection(DEFAULT_COLUMNS.index("Artist"), 333)
    expected_order = ["Song", "Artist", "Duration", "Year", "Album", "Track"]
    assert first.column_order() == expected_order
    assert other.column_order() == expected_order
    assert other.columnWidth(DEFAULT_COLUMNS.index("Artist")) == 333

    # Data still comes from the logical columns, whatever the visual order.
    assert first.item(0, PATH_COLUMN).data(Qt.UserRole) == songs[0]

    window.add_playlist()
    created = window.current_table()
    assert created.column_order() == expected_order
    assert created.columnWidth(DEFAULT_COLUMNS.index("Artist")) == 333

    # A new custom tag column goes last, and the layout survives rebuilding the tables.
    window.tags_input.setText("rock")
    window.apply_custom_tags()
    assert first.column_order() == expected_order + ["rock"]
    assert first.columnWidth(DEFAULT_COLUMNS.index("Artist")) == 333

    window.close()
    monkeypatch.setattr(main_window_module, "app_data_dir", lambda: tmp_path)
    reopened = MainWindow()
    try:
        for index in range(reopened.tabs.count()):
            table = reopened.tabs.widget(index)
            assert table.column_order() == expected_order + ["rock"]
            assert table.columnWidth(DEFAULT_COLUMNS.index("Artist")) == 333
    finally:
        reopened.close()
        reopened.deleteLater()


def test_sorting_by_year_keeps_the_column_layout(window, tmp_path, monkeypatch):
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(3)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    table = window.current_table()
    header = table.horizontalHeader()
    header.moveSection(header.visualIndex(DEFAULT_COLUMNS.index("Album")), 0)
    order = table.column_order()
    widths = dict(window.settings.column_widths)

    table.reorder(list(reversed(songs)))
    assert table.column_order() == order
    assert window.settings.column_widths == widths


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


def test_header_clicks_start_ascending_and_flip(filtered_window):
    window = filtered_window
    table = window.current_table()
    header = table.horizontalHeader()
    artist, album = DEFAULT_COLUMNS.index("Artist"), DEFAULT_COLUMNS.index("Album")

    def click(column):
        section = header.sectionViewportPosition(column) + header.sectionSize(column) // 2
        QTest.mouseClick(header.viewport(), Qt.LeftButton, pos=QPoint(section, 5))

    def column_values(column):
        return [table.item(row, column).text() for row in range(table.rowCount())]

    steps = [
        (artist, Qt.AscendingOrder),
        (artist, Qt.DescendingOrder),
        (album, Qt.AscendingOrder),
        (artist, Qt.AscendingOrder),
        (album, Qt.AscendingOrder),
        (album, Qt.DescendingOrder),
        (album, Qt.AscendingOrder),
    ]
    for column, order in steps:
        click(column)
        assert header.sortIndicatorSection() == column
        assert header.sortIndicatorOrder() == order
        values = column_values(column)
        assert values == sorted(values, reverse=order == Qt.DescendingOrder)


def test_tag_column_clicks_start_descending(filtered_window):
    window = filtered_window
    window.tags_input.setText("rock")
    window.apply_custom_tags()
    table = window.current_table()
    header = table.horizontalHeader()
    tag, artist = len(DEFAULT_COLUMNS), DEFAULT_COLUMNS.index("Artist")

    for column, order in [
        (tag, Qt.DescendingOrder),
        (tag, Qt.AscendingOrder),
        (tag, Qt.DescendingOrder),
        (artist, Qt.AscendingOrder),
        (tag, Qt.DescendingOrder),
    ]:
        table.sort_by_column(column)
        assert header.sortIndicatorSection() == column
        assert header.sortIndicatorOrder() == order


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


def test_version_shows_in_window_title_and_splash(window):
    from tag_gui import __version__
    from tag_gui.ui.splash import Splash

    assert __version__ in window.windowTitle()
    assert __version__ in Splash().version.text()


def test_playback_feeds_the_last_fm_play_tracker(window, tmp_path, monkeypatch):
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    monkeypatch.setattr(window.player, "play", lambda: None)
    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(2)]
    window.add_tracks_to_current_playlist(songs)

    window.play_row(1)
    tracker = window.lastfm.tracker
    assert tracker.track == songs[1]
    window.on_duration_changed(180_000)
    assert tracker.duration_ms == 180_000
    window.on_playback_state_changed(QMediaPlayer.PausedState)
    paused = tracker.listened_ms()
    QTest.qWait(50)
    assert tracker.listened_ms() == paused


def test_track_column_follows_album_and_sorts_by_number(window, tmp_path, monkeypatch):
    from tag_gui.constants import TRACK_COLUMN
    from tag_gui.core.tags import set_standard_tags

    songs = []
    for name, number in (("a", "10"), ("b", "2/12"), ("c", ""), ("d", "1")):
        song = write_flac(tmp_path / f"{name}.flac")
        if number:
            set_standard_tags(song, {"tracknumber": number})
        songs.append(str(song))
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    table = window.current_table()
    assert DEFAULT_COLUMNS[TRACK_COLUMN - 1] == "Album"

    def tracks():
        return [table.item(row, TRACK_COLUMN).text() for row in range(table.rowCount())]

    assert tracks() == ["10", "2", "", "1"]
    table.sort_by_column(TRACK_COLUMN)
    assert table.horizontalHeader().sortIndicatorOrder() == Qt.AscendingOrder
    assert tracks() == ["", "1", "2", "10"]
    table.sort_by_column(TRACK_COLUMN)
    assert tracks() == ["10", "2", "1", ""]


def test_a_saved_column_order_gets_the_new_track_column_after_album(window):
    window.settings.column_order = ["Song", "Album", "Artist", "Duration", "Year"]
    window.add_playlist()
    order = window.current_table().column_order()
    assert order == ["Song", "Album", "Track", "Artist", "Duration", "Year"]


def test_view_all_metadata_edits_the_file_and_refreshes_the_rows(window, tmp_path, monkeypatch):
    from tag_gui.core.tags import set_standard_tags
    from tag_gui.ui import tag_actions
    from tag_gui.ui.metadata_dialog import VALUE_COL

    song = write_flac(tmp_path / "song.flac")
    set_standard_tags(song, {"title": "Old title", "artist": "Kaija"})
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.tags_input.setText("rock")
    window.apply_custom_tags()
    window.add_tracks_to_current_playlist([str(song)])
    window.add_playlist()
    window.add_tracks_to_current_playlist([str(song)])
    tables = [window.tabs.widget(0), window.tabs.widget(1)]

    def edit_and_save(dialog):
        assert dialog.table.item(0, 0).text() == "Title"
        dialog.table.item(0, VALUE_COL).setText("New title")
        row = dialog._add_row("(new field)", "rock", "X", True)
        assert dialog.table.item(row, VALUE_COL).text() == "X"
        dialog.accept()
        return 1

    monkeypatch.setattr(tag_actions.MetadataDialog, "exec", edit_and_save)
    window.view_metadata(str(song))

    song_column = DEFAULT_COLUMNS.index("Song")
    rock_column = len(DEFAULT_COLUMNS)
    for table in tables:
        assert table.item(0, song_column).text() == "New title"
        assert table.item(0, rock_column).checkState() == Qt.Checked
    assert window.metadata.get(str(song), ["rock"]).tag_states == {"rock": True}


def test_metadata_dialog_keeps_open_when_saving_fails(qapp, tmp_path, monkeypatch):
    from tag_gui.core.file_metadata import read_file_metadata
    from tag_gui.ui import metadata_dialog
    from tag_gui.ui.metadata_dialog import MetadataDialog, VALUE_COL

    song = write_flac(tmp_path / "song.flac")
    warnings = []
    monkeypatch.setattr(
        metadata_dialog.QMessageBox, "warning", lambda *args: warnings.append(args[2])
    )

    def failing_save(changes):
        raise ValueError("disk full")

    dialog = MetadataDialog(song, read_file_metadata(song), failing_save)
    row = dialog._add_row("(new field)", "MOOD", "calm", True)
    assert dialog.table.item(row, VALUE_COL).text() == "calm"
    dialog.accept()
    assert warnings == ["disk full"]
    assert dialog.result() != MetadataDialog.Accepted


def test_missing_track_numbers_are_read_in_the_background(window, tmp_path, monkeypatch):
    from tag_gui.constants import TRACK_COLUMN
    from tag_gui.core.tags import set_standard_tags

    songs = []
    for index in range(3):
        song = write_flac(tmp_path / f"n{index}.flac")
        set_standard_tags(song, {"tracknumber": str(index + 5)})
        songs.append(str(song))
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist(songs)
    table = window.current_table()
    # As if loaded from a cache written before the Track column existed.
    for row, track in enumerate(songs):
        info = window.metadata.get(track, [])
        info.position = None
        info.fields[-1] = ""
        table.item(row, TRACK_COLUMN).setText("")

    window.fill_missing_track_numbers()
    assert wait_until(lambda: window._track_number_worker is None)
    QTest.qWait(50)
    assert [table.item(row, TRACK_COLUMN).text() for row in range(3)] == ["5", "6", "7"]
    assert window.metadata.cached_position(songs[0]) == (0, 5)


def test_ticking_a_tag_shows_in_every_playlist_with_the_file(window, tmp_path, monkeypatch):
    from tag_gui.core.tags import read_custom_tag_states
    from tag_gui.ui import tag_actions

    songs = [str(write_flac(tmp_path / f"song{i}.flac")) for i in range(3)]
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.tags_input.setText("rock, calm")
    window.apply_custom_tags()
    window.add_tracks_to_current_playlist(songs)
    window.add_playlist()
    window.add_tracks_to_current_playlist([songs[2], songs[1]])
    first, second = window.tabs.widget(0), window.tabs.widget(1)
    rock, calm = len(DEFAULT_COLUMNS), len(DEFAULT_COLUMNS) + 1
    writes = []
    write = tag_actions.set_custom_tag
    monkeypatch.setattr(
        tag_actions, "set_custom_tag", lambda *args: (writes.append(args), write(*args))
    )

    first.item(1, rock).setCheckState(Qt.Checked)
    assert second.item(1, rock).checkState() == Qt.Checked
    assert second.item(0, rock).checkState() == Qt.Unchecked
    assert second.item(1, calm).checkState() == Qt.Unchecked

    second.item(1, rock).setCheckState(Qt.Unchecked)
    assert first.item(1, rock).checkState() == Qt.Unchecked
    # Mirroring into the other playlist must not write the file again.
    assert len(writes) == 2
    assert read_custom_tag_states(tmp_path / "song1.flac", ["rock"]) == {"rock": False}


def test_edit_tags_shows_in_every_playlist_with_the_file(window, tmp_path, monkeypatch):
    from tag_gui.ui import tag_actions

    song = str(write_flac(tmp_path / "song.flac"))
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.add_tracks_to_current_playlist([song])
    window.add_playlist()
    window.add_tracks_to_current_playlist([song])
    monkeypatch.setattr(tag_actions.StandardTagsDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(
        tag_actions.StandardTagsDialog, "changed_values", lambda self: {"album": "Renamed"}
    )

    window.current_table().selectRow(0)
    window.edit_selected_tags()

    album = DEFAULT_COLUMNS.index("Album")
    assert [window.tabs.widget(i).item(0, album).text() for i in range(2)] == ["Renamed"] * 2


def test_added_tracks_go_last_and_leave_the_album_shades_alone(window, tmp_path, monkeypatch):
    songs = tagged_songs(
        tmp_path, [("Artist", f"Song {i}", f"Album {i // 2}", "2000") for i in range(8)]
    )
    monkeypatch.setattr(MainWindow, "scan_for_audio_files", lambda self, paths: list(paths))
    window.tags_input.setText("rock")
    window.apply_custom_tags()
    window.add_tracks_to_current_playlist(songs[:5])
    table = window.current_table()
    rock = len(DEFAULT_COLUMNS)
    table.sort_by_column(rock)
    # Checked rows sort first, so a rebuild would move this row up and flip every shade.
    table.item(3, rock).setCheckState(Qt.Checked)

    def shades():
        return [
            (table.item(row, PATH_COLUMN).data(Qt.UserRole), table.row_background(row).color())
            for row in range(table.rowCount())
        ]

    before = shades()
    window.add_tracks_to_current_playlist(songs[5:7])

    after = shades()
    assert after[:5] == before
    assert [track for track, _color in after[5:]] == songs[5:7]
    # Song 5 finishes the album of song 4; song 6 starts the next one.
    assert after[5][1] == after[4][1] != after[6][1]
    assert window.current_playlist().tracks == songs[:7]
