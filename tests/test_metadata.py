import json
import os

import pytest

from tag_gui.core import metadata as metadata_module
from tag_gui.core.metadata import CACHE_VERSION, MetadataCache


@pytest.fixture
def reads(monkeypatch):
    """Count disk reads so caching can be observed without touching real audio files."""
    counts = {"fields": 0, "tags": 0}

    def fake_fields(path):
        counts["fields"] += 1
        return ["Kaija", "00:03", path.stem, "1999", "Talvi"]

    def fake_states(path, tag_names):
        counts["tags"] += 1
        return {tag: tag == "rock" for tag in tag_names}

    monkeypatch.setattr(metadata_module, "track_fields", fake_fields)
    monkeypatch.setattr(metadata_module, "read_custom_tag_states", fake_states)
    return counts


@pytest.fixture
def song(tmp_path):
    path = tmp_path / "song.mp3"
    path.write_bytes(b"x")
    return path


def test_first_read_fills_fields_and_tag_states(reads, song):
    info = MetadataCache().get(str(song), ["rock", "jazz"])
    assert info.fields[0] == "Kaija"
    assert info.tag_states == {"rock": True, "jazz": False}


def test_second_read_comes_from_the_cache(reads, song):
    cache = MetadataCache()
    cache.get(str(song), ["rock"])
    cache.get(str(song), ["rock"])
    assert reads["fields"] == 1


def test_a_changed_file_is_read_again(reads, song):
    cache = MetadataCache()
    cache.get(str(song), ["rock"])
    os.utime(song, (0, 0))
    cache.get(str(song), ["rock"])
    assert reads["fields"] == 2


def test_a_new_tag_is_topped_up_without_rereading_fields(reads, song):
    cache = MetadataCache()
    cache.get(str(song), ["rock"])
    info = cache.get(str(song), ["rock", "jazz"])
    assert info.tag_states == {"rock": True, "jazz": False}
    assert reads["fields"] == 1
    assert reads["tags"] == 2


def test_update_tag_state_avoids_a_reread(reads, song):
    cache = MetadataCache()
    cache.get(str(song), ["rock"])
    cache.update_tag_state(str(song), "rock", False)
    assert cache.get(str(song), ["rock"]).tag_states["rock"] is False
    assert reads["fields"] == 1


def test_discard_forces_the_next_read(reads, song):
    cache = MetadataCache()
    cache.get(str(song), ["rock"])
    cache.discard(str(song))
    cache.get(str(song), ["rock"])
    assert reads["fields"] == 2


def test_save_and_load_round_trip(reads, song, tmp_path):
    path = tmp_path / "metadata.json"
    cache = MetadataCache(path)
    cache.get(str(song), ["rock"])
    cache.save()

    reloaded = MetadataCache(path)
    reloaded.load()
    assert reloaded.get(str(song), ["rock"]).fields[0] == "Kaija"
    assert reads["fields"] == 1


def test_save_drops_tracks_that_are_no_longer_in_a_playlist(reads, song, tmp_path):
    path = tmp_path / "metadata.json"
    cache = MetadataCache(path)
    cache.get(str(song), ["rock"])
    cache.save(keep=set())
    assert json.loads(path.read_text(encoding="utf-8"))["tracks"] == {}


def test_load_discards_an_older_cache_version(reads, song, tmp_path):
    path = tmp_path / "metadata.json"
    path.write_text(
        json.dumps({"version": CACHE_VERSION - 1, "tracks": {str(song): {"fields": [], "mtime": 0}}}),
        encoding="utf-8",
    )
    cache = MetadataCache(path)
    cache.load()
    cache.get(str(song), ["rock"])
    assert reads["fields"] == 1


def test_load_survives_a_corrupt_file(reads, tmp_path):
    path = tmp_path / "metadata.json"
    path.write_text("{not json", encoding="utf-8")
    cache = MetadataCache(path)
    cache.load()  # must not raise


def test_load_skips_malformed_entries(reads, song, tmp_path):
    path = tmp_path / "metadata.json"
    path.write_text(
        json.dumps({"version": CACHE_VERSION, "tracks": {str(song): {"mtime": "soon"}}}),
        encoding="utf-8",
    )
    cache = MetadataCache(path)
    cache.load()
    cache.get(str(song), ["rock"])
    assert reads["fields"] == 1


def test_saving_an_unchanged_cache_writes_nothing(reads, song, tmp_path):
    path = tmp_path / "metadata.json"
    MetadataCache(path).save()
    assert not path.exists()
