import pytest
from mutagen import File
from mutagen.id3 import APIC, COMM, TCON, TIT2, TPE1, TRCK, TXXX
from mutagen.flac import Picture

from tag_gui.core.file_metadata import (
    TagEntry,
    changed_fields,
    read_file_metadata,
    write_file_metadata,
)
from tag_gui.core.tags import set_standard_tags


def add_id3(path, *frames):
    audio = File(str(path))
    audio.add_tags()
    for frame in frames:
        audio.tags.add(frame)
    audio.save()


def keys_and_values(metadata):
    return [(entry.key, entry.value) for entry in metadata.entries]


def test_mp3_tags_come_in_the_standard_order_then_file_order(mp3):
    add_id3(
        mp3,
        TXXX(encoding=3, desc="rock", text=["X"]),
        TCON(encoding=3, text=["Metal"]),
        TIT2(encoding=3, text=["Aces High"]),
        APIC(encoding=3, mime="image/png", type=3, desc="", data=b"x" * 3000),
        TPE1(encoding=3, text=["Iron Maiden", "Bruce"]),
        TRCK(encoding=3, text=["1/8"]),
    )
    metadata = read_file_metadata(mp3)
    assert metadata.kind == "id3"
    assert keys_and_values(metadata)[:5] == [
        ("TIT2", "Aces High"),
        ("TPE1", "Iron Maiden"),
        ("TPE1", "Bruce"),
        ("TRCK", "1/8"),
        ("TCON", "Metal"),
    ]
    labels = {entry.key: entry.label for entry in metadata.entries}
    assert labels["TIT2"] == "Title" and labels["TXXX:rock"] == "rock (custom text)"
    picture = metadata.entries[-1]
    assert picture.label == "Picture" and not picture.editable
    info = dict(metadata.info)
    assert info["File"] == str(mp3) and info["Bitrate"] == "128 kbps"


def test_flac_tags_and_pictures(flac):
    set_standard_tags(flac, {"genre": "Rock", "artist": "Kaija", "title": "Talvi"})
    audio = File(str(flac))
    audio.tags["MOOD"] = ["calm"]
    picture = Picture()
    picture.mime, picture.width, picture.height, picture.data = "image/jpeg", 10, 10, b"x" * 2048
    audio.add_picture(picture)
    audio.save()

    metadata = read_file_metadata(flac)
    assert metadata.kind == "vorbis"
    assert [entry.label for entry in metadata.entries] == [
        "Title",
        "Artist",
        "Genre",
        "Mood",
        "Picture",
    ]
    assert metadata.entries[-1].value == "image/jpeg, 10x10, 2 KB"


def test_editing_mp3_values_keeps_other_frames(mp3):
    add_id3(
        mp3,
        TIT2(encoding=3, text=["Old"]),
        TPE1(encoding=3, text=["A", "B"]),
        COMM(encoding=3, lang="eng", desc="", text=["note"]),
        APIC(encoding=3, mime="image/png", type=3, desc="", data=b"png"),
    )
    before = read_file_metadata(mp3)
    after = [(e.key, e.value) for e in before.entries if e.editable]
    after = [(k, {"Old": "New", "B": ""}.get(v, v)) for k, v in after]
    after += [("TCOM", "Bach"), ("TXXX:Mood", "calm")]
    changes = changed_fields(before.entries, after)
    assert changes == {"TIT2": ["New"], "TPE1": ["A"], "TCOM": ["Bach"], "TXXX:Mood": ["calm"]}

    write_file_metadata(mp3, changes)
    assert keys_and_values(read_file_metadata(mp3)) == [
        ("TIT2", "New"),
        ("TPE1", "A"),
        ("TCOM", "Bach"),
        ("COMM::eng", "note"),
        ("TXXX:Mood", "calm"),
        ("APIC:", "cover front,  (image/png, 3 bytes)"),
    ]


def test_mp3_rejects_keys_that_are_not_text_frames(mp3):
    with pytest.raises(ValueError, match="TXXX:Name"):
        write_file_metadata(mp3, {"Mood": ["calm"]})
    with pytest.raises(ValueError, match="needs a name"):
        write_file_metadata(mp3, {"TXXX": ["calm"]})


def test_flac_fields_can_be_added_changed_and_removed(flac):
    write_file_metadata(flac, {"TITLE": ["Talvi"], "ARTIST": ["A", "B"], "MOOD": ["calm"]})
    assert keys_and_values(read_file_metadata(flac)) == [
        ("TITLE", "Talvi"),
        ("ARTIST", "A"),
        ("ARTIST", "B"),
        ("MOOD", "calm"),
    ]
    write_file_metadata(flac, {"MOOD": [], "ARTIST": ["C"]})
    assert keys_and_values(read_file_metadata(flac)) == [("TITLE", "Talvi"), ("ARTIST", "C")]
    with pytest.raises(ValueError, match="valid field name"):
        write_file_metadata(flac, {"A=B": ["x"]})


def test_a_multi_line_value_locks_its_whole_field(flac):
    write_file_metadata(flac, {"LYRICS": ["one", "two\nlines"], "TITLE": ["Talvi"]})
    editable = {entry.key: entry.editable for entry in read_file_metadata(flac).entries}
    assert editable == {"TITLE": True, "LYRICS": False}


def test_changed_fields_ignores_untouched_and_empty_new_fields():
    before = [
        TagEntry("TITLE", "Title", "Talvi", True),
        TagEntry("(picture)", "Picture", "png", False),
    ]
    assert changed_fields(before, [("TITLE", "Talvi")]) == {}
    assert changed_fields(before, [("TITLE", "Talvi"), ("MOOD", "  ")]) == {}
    assert changed_fields(before, [("TITLE", "")]) == {"TITLE": []}
    assert changed_fields(before, []) == {"TITLE": []}


def test_a_tagless_file_can_get_its_first_tags(mp3):
    metadata = read_file_metadata(mp3)
    assert metadata.entries == [] and metadata.can_add
    write_file_metadata(mp3, {"TIT2": ["First"]})
    assert keys_and_values(read_file_metadata(mp3)) == [("TIT2", "First")]
