import random

import pytest

from tag_gui.core.shuffle import TrackKey, normalize_title, pick_next, same_title


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Songtitle (Cover)", "songtitle"),
        ("Songtitle [Live]", "songtitle"),
        ("Songtitle Live 2018", "songtitle"),
        ("Songtitle - Live at Wembley", "songtitle"),
        ("Songtitle - Remastered 2011", "songtitle"),
        ("Songtitle Live at the Apollo", "songtitle"),
        ("Söngtitle (Demo) Remastered", "songtitle"),
        ("Live and Let Die", "live and let die"),
        ("I Live for You", "i live for you"),
        ("Live", "live"),
        ("Rock 'n' Roll", "rock n roll"),
    ],
)
def test_normalize_title_strips_version_notes(title, expected):
    assert normalize_title(title) == expected


def test_same_title_tolerates_small_differences_only():
    assert same_title("songtitle", "songtitle")
    assert same_title("enter sandman", "enter sandmann")
    assert not same_title("one", "two")
    assert not same_title("", "")


def test_track_keys_clash_on_artist_album_or_song():
    base = TrackKey.of("Metallica", "Black Album", "Enter Sandman")
    assert base.clashes_with(TrackKey.of("METALLICA", "Load", "Until It Sleeps"))
    assert base.clashes_with(TrackKey.of("Various", "Black Album", "Other"))
    assert base.clashes_with(TrackKey.of("Motörhead", "Covers", "Enter Sandman (Cover)"))
    assert not base.clashes_with(TrackKey.of("Slayer", "Reign in Blood", "Angel of Death"))
    # Missing tags never count as a match.
    assert not TrackKey.of("", "", "a").clashes_with(TrackKey.of("", "", "b"))


LIBRARY = {
    "m1": ("Metallica", "Black", "Enter Sandman"),
    "m2": ("Metallica", "Black", "Sad but True"),
    "s1": ("Slayer", "Reign", "Angel of Death"),
    "c1": ("Motorhead", "Covers", "Enter Sandman (Live 2005)"),
    "b1": ("Bathory", "Blood", "One Rode to Asa Bay"),
}


def key_of(track):
    return TrackKey.of(*LIBRARY[track])


def test_pick_next_avoids_recent_artist_album_and_song():
    for seed in range(30):
        choice = pick_next(list(LIBRARY), key_of, recent=["m1"], rng=random.Random(seed))
        assert choice in ("s1", "b1")


def test_pick_next_prefers_tracks_not_played_this_round():
    for seed in range(30):
        choice = pick_next(
            list(LIBRARY), key_of, recent=["m1"], played={"m1", "s1"}, rng=random.Random(seed)
        )
        assert choice == "b1"


def test_pick_next_relaxes_the_history_when_everything_clashes():
    tracks = ["m1", "m2"]
    assert pick_next(tracks, key_of, recent=["m1"]) == "m2"
    assert pick_next(["m1"], key_of, recent=["m1"]) == "m1"
    assert pick_next([], key_of, recent=[]) is None


def test_only_the_last_ten_tracks_count():
    library = {f"t{i}": (f"Artist {i}", f"Album {i}", f"Song {i}") for i in range(12)}
    recent = [f"t{i}" for i in range(11)]  # t0 dropped out of the window
    choice = pick_next(list(library), lambda t: TrackKey.of(*library[t]), recent=recent)
    assert choice in ("t0", "t11")
