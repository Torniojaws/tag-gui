import random

from tag_gui.core.sorting import SortFields, by_path, by_year, shuffled

# path -> (year, album, title, disc, track)
LIBRARY = {
    "/m/b2.flac": ("2026", "Album B", "B two", 0, 2),
    "/m/a1.flac": ("2026", "Album A", "A one", 0, 1),
    "/m/old2.flac": ("1959", "Oldies", "Old two", 0, 2),
    "/m/notag.flac": ("", "", "notag", 0, 0),
    "/m/a2.flac": ("2026", "Album A", "A two", 0, 2),
    "/m/b1.flac": ("2026", "Album B", "B one", 0, 1),
    "/m/old1.flac": ("1959", "Oldies", "Old one", 0, 1),
    "/m/mid.flac": ("1990", "Middle", "Middle", 0, 1),
}


def fields_of(path):
    return SortFields(*LIBRARY[path])


def test_by_path_orders_full_paths_ignoring_case():
    assert by_path(["/b/x.mp3", "/A/z.mp3", "/a/y.mp3"]) == ["/a/y.mp3", "/A/z.mp3", "/b/x.mp3"]


def test_shuffled_keeps_every_track_and_differs_between_runs():
    tracks = [f"/m/{i}.mp3" for i in range(50)]
    first = shuffled(tracks, random.Random(1))
    second = shuffled(tracks, random.Random(2))
    assert sorted(first) == sorted(tracks)
    assert first != second
    assert tracks == [f"/m/{i}.mp3" for i in range(50)]


def test_oldest_first_keeps_album_order_within_a_year_and_untagged_last():
    assert by_year(list(LIBRARY), fields_of) == [
        "/m/old1.flac",
        "/m/old2.flac",
        "/m/mid.flac",
        # Album B appears first in the playlist, so it stays ahead of Album A.
        "/m/b1.flac",
        "/m/b2.flac",
        "/m/a1.flac",
        "/m/a2.flac",
        "/m/notag.flac",
    ]


def test_newest_first_still_orders_tracks_within_each_album():
    assert by_year(list(LIBRARY), fields_of, newest_first=True) == [
        "/m/b1.flac",
        "/m/b2.flac",
        "/m/a1.flac",
        "/m/a2.flac",
        "/m/mid.flac",
        "/m/old1.flac",
        "/m/old2.flac",
        "/m/notag.flac",
    ]


def test_albums_without_track_numbers_sort_by_title_then_path():
    library = {
        "/m/2/song.flac": ("2000", "Album", "Same", 0, 0),
        "/m/1/song.flac": ("2000", "Album", "Same", 0, 0),
        "/m/c.flac": ("2000", "Album", "alpha", 0, 0),
        "/m/d.flac": ("2000", "Album", "Beta", 0, 0),
    }
    result = by_year(list(library), lambda path: SortFields(*library[path]))
    assert result == ["/m/c.flac", "/m/d.flac", "/m/1/song.flac", "/m/2/song.flac"]


def test_discs_and_numbered_tracks_come_before_unnumbered_ones():
    library = {
        "/m/loose.flac": ("2000", "Album", "Aaa", 0, 0),
        "/m/d2t1.flac": ("2000", "Album", "Zzz", 2, 1),
        "/m/d1t2.flac": ("2000", "Album", "Yyy", 1, 2),
        "/m/d1t1.flac": ("2000", "Album", "Xxx", 1, 1),
    }
    result = by_year(list(library), lambda path: SortFields(*library[path]))
    assert result == ["/m/d1t1.flac", "/m/d1t2.flac", "/m/d2t1.flac", "/m/loose.flac"]


def test_year_only_tracks_without_album_keep_their_order():
    library = {
        "/m/x.flac": ("2001", "", "x", 0, 0),
        "/m/y.flac": ("1999", "", "y", 0, 0),
        "/m/z.flac": ("2001", "", "z", 0, 0),
        "/m/w.flac": ("abcd", "Album", "w", 0, 1),
    }
    result = by_year(list(library), lambda path: SortFields(*library[path]))
    assert result == ["/m/y.flac", "/m/x.flac", "/m/z.flac", "/m/w.flac"]
