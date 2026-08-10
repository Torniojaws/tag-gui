import json

import pytest

from tag_gui.core.models import Playlist
from tag_gui.core.playlists import PlaylistStore


@pytest.fixture
def store(tmp_path):
    return PlaylistStore(tmp_path)


def test_load_without_a_state_file_creates_the_default(store):
    assert store.load() == 0
    assert [p.name for p in store.playlists] == ["default"]


def test_save_and_load_round_trip(store, tmp_path):
    store.playlists = [
        Playlist(name="Yömusa", file_name="yomusa.m3u", tracks=["a.mp3", "b.flac"]),
        Playlist(name="Toinen", file_name="toinen.m3u"),
    ]
    store.save(active_index=1)

    reloaded = PlaylistStore(tmp_path)
    assert reloaded.load() == 1
    assert [p.name for p in reloaded.playlists] == ["Yömusa", "Toinen"]
    assert reloaded.playlists[0].tracks == ["a.mp3", "b.flac"]


def test_m3u_keeps_the_display_name_in_a_header(store, tmp_path):
    playlist = Playlist(name="Yömusa", file_name="yomusa.m3u", tracks=["a.mp3"])
    store.playlists = [playlist]
    store.write_m3u(playlist)
    text = (tmp_path / "yomusa.m3u").read_text(encoding="utf-8")
    assert text.splitlines() == ["#EXTM3U", "#PLAYLIST:Yömusa", "a.mp3"]


def test_read_m3u_skips_comments_and_blank_lines(tmp_path):
    path = tmp_path / "list.m3u"
    path.write_text("#EXTM3U\n#PLAYLIST:Nimi\n\n#EXTINF:1,x\na.mp3\n", encoding="utf-8")
    assert PlaylistStore.read_m3u(path) == ("Nimi", ["a.mp3"])


def test_read_m3u_of_a_missing_file(tmp_path):
    assert PlaylistStore.read_m3u(tmp_path / "gone.m3u") == ("", [])


def test_path_for_keeps_loaded_playlists_where_they_live(store, tmp_path):
    outside = tmp_path.parent / "elsewhere" / "mix.m3u"
    assert store.path_for(Playlist(name="mix", file_name=str(outside))) == outside
    assert store.path_for(Playlist(name="own", file_name="own.m3u")) == tmp_path / "own.m3u"


def test_unique_file_name_adds_a_suffix(store):
    store.playlists = [Playlist(name="a", file_name="default.m3u")]
    assert store.unique_file_name("default.m3u") == "default-2.m3u"
    assert store.unique_file_name("default.m3u", skip_index=0) == "default.m3u"


def test_unique_file_name_counts_past_existing_suffixes(store):
    store.playlists = [
        Playlist(name="a", file_name="default.m3u"),
        Playlist(name="b", file_name="Default-2.m3u"),
    ]
    assert store.unique_file_name("default.m3u") == "default-3.m3u"


def test_next_default_names_are_numbered(store):
    store.playlists = []
    assert store.next_default().name == "default"
    store.playlists = [Playlist(name="default", file_name="default.m3u")]
    assert store.next_default().name == "default2"


def test_rename_moves_the_file(store, tmp_path):
    store.playlists = [Playlist(name="default", file_name="default.m3u", tracks=["a.mp3"])]
    store.save(0)
    assert store.rename(0, "Yömusa") is True
    assert store.playlists[0].file_name == "yomusa.m3u"
    assert (tmp_path / "yomusa.m3u").exists()
    assert not (tmp_path / "default.m3u").exists()


def test_rename_of_a_loaded_playlist_stays_in_its_folder(store, tmp_path):
    outside = tmp_path.parent / "elsewhere"
    outside.mkdir(exist_ok=True)
    store.playlists = [Playlist(name="mix", file_name=str(outside / "mix.m3u"))]
    store.rename(0, "New Mix")
    assert store.path_for(store.playlists[0]) == outside / "new-mix.m3u"


def test_rename_rejects_blank_and_unchanged_names(store):
    store.playlists = [Playlist(name="default", file_name="default.m3u")]
    assert store.rename(0, "   ") is False
    assert store.rename(0, "default") is False
    assert store.playlists[0].name == "default"


def test_move_reorders_the_playlists(store):
    store.playlists = [Playlist(name=n, file_name=f"{n}.m3u") for n in ("a", "b", "c")]
    store.move(0, 2)
    assert [p.name for p in store.playlists] == ["b", "c", "a"]


def test_all_tracks_is_the_union(store):
    store.playlists = [
        Playlist(name="a", file_name="a.m3u", tracks=["x.mp3", "y.mp3"]),
        Playlist(name="b", file_name="b.m3u", tracks=["y.mp3", "z.mp3"]),
    ]
    assert store.all_tracks() == {"x.mp3", "y.mp3", "z.mp3"}


def test_load_accepts_a_hand_written_state_file(store, tmp_path):
    (tmp_path / "playlists.json").write_text(
        json.dumps({"active_index": "2", "playlists": [{"name": "a", "file_name": "a.m3u"}]}),
        encoding="utf-8",
    )
    assert store.load() == 2
    assert [p.name for p in store.playlists] == ["a"]
