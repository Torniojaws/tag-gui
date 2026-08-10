import pytest

from tag_gui.core.tags import (
    ascii_tag_key,
    custom_tag_checked,
    get_duration,
    load_easy_tags,
    load_raw_tags,
    normalize_tag_name,
    parse_custom_tags,
    read_custom_tag_states,
    set_custom_tag,
    set_standard_tags,
)


def test_parse_custom_tags_trims_and_drops_blanks():
    assert parse_custom_tags(" rock , , jazz ") == ["rock", "jazz"]


def test_parse_custom_tags_drops_ascii_equivalent_duplicates():
    # All three are stored as "Yomusa", so keeping them would write one tag three times.
    assert parse_custom_tags("Yömusa, yomusa, YOMUSA") == ["Yömusa"]


def test_parse_custom_tags_of_empty_text():
    assert parse_custom_tags("") == []


def test_ascii_tag_key_strips_accents():
    assert ascii_tag_key("Yömusa") == "Yomusa"


def test_ascii_tag_key_replaces_characters_that_break_the_frame():
    assert ascii_tag_key("a=b") == "a_b"
    assert ascii_tag_key("näin~") == "nain_"


def test_normalize_tag_name_ignores_case_and_accents():
    assert normalize_tag_name("Yömusa") == normalize_tag_name("YOMUSA")


def test_custom_tag_round_trip(track):
    set_custom_tag(track, "Yömusa", True)
    assert read_custom_tag_states(track, ["Yömusa"]) == {"Yömusa": True}


def test_custom_tag_can_be_unchecked(track):
    set_custom_tag(track, "rock", True)
    set_custom_tag(track, "rock", False)
    assert read_custom_tag_states(track, ["rock"]) == {"rock": False}


def test_custom_tag_lookup_ignores_case(track):
    set_custom_tag(track, "Rock", True)
    assert custom_tag_checked(load_raw_tags(track), "rOcK") is True


def test_setting_a_tag_twice_leaves_one_copy(track):
    set_custom_tag(track, "rock", True)
    set_custom_tag(track, "rock", True)
    set_custom_tag(track, "rock", False)
    assert read_custom_tag_states(track, ["rock"]) == {"rock": False}


def test_unset_tags_read_as_unchecked(track):
    set_custom_tag(track, "rock", True)
    assert read_custom_tag_states(track, ["rock", "jazz"]) == {"rock": True, "jazz": False}


def test_custom_tags_do_not_disturb_each_other(track):
    set_custom_tag(track, "rock", True)
    set_custom_tag(track, "jazz", True)
    set_custom_tag(track, "rock", False)
    assert read_custom_tag_states(track, ["rock", "jazz"]) == {"rock": False, "jazz": True}


def test_custom_tag_of_a_file_without_tags_is_unchecked(track):
    assert read_custom_tag_states(track, ["rock"]) == {"rock": False}


def test_standard_tags_are_written(track):
    set_standard_tags(track, {"artist": "Kaija", "title": "Laulu"})
    easy = load_easy_tags(track)
    assert easy["artist"] == ["Kaija"]
    assert easy["title"] == ["Laulu"]


def test_standard_tags_are_cleared_by_an_empty_value(track):
    set_standard_tags(track, {"artist": "Kaija"})
    set_standard_tags(track, {"artist": ""})
    assert "artist" not in load_easy_tags(track)


def test_writing_one_standard_tag_leaves_the_others(track):
    set_standard_tags(track, {"artist": "Kaija", "album": "Talvi"})
    set_standard_tags(track, {"artist": "Mika"})
    assert load_easy_tags(track)["album"] == ["Talvi"]


def test_standard_tags_survive_a_custom_tag_write(track):
    set_standard_tags(track, {"artist": "Kaija"})
    set_custom_tag(track, "rock", True)
    assert load_easy_tags(track)["artist"] == ["Kaija"]


def test_set_standard_tags_rejects_an_unreadable_file(tmp_path):
    junk = tmp_path / "not-audio.mp3"
    junk.write_bytes(b"this is not audio")
    with pytest.raises(ValueError):
        set_standard_tags(junk, {"artist": "Kaija"})


def test_set_custom_tag_ignores_an_unreadable_file(tmp_path):
    junk = tmp_path / "not-audio.mp3"
    junk.write_bytes(b"this is not audio")
    set_custom_tag(junk, "rock", True)
    assert junk.read_bytes() == b"this is not audio"


def test_get_duration_reads_the_stream_length(flac):
    assert get_duration(flac) == "00:03"


def test_get_duration_of_an_unreadable_file(tmp_path):
    junk = tmp_path / "not-audio.mp3"
    junk.write_bytes(b"this is not audio")
    assert get_duration(junk) == "00:00"
