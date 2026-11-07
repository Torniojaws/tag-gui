"""Every tag of a file, in a standard order, plus writing edited tags back.

Tags are shown one value per entry, so a field with two artists becomes two entries with the
same key and nothing is lost by joining and splitting values. Text values can be edited;
pictures, binary frames and multi-line text are shown read-only.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from mutagen.asf import ASFTags, ASFUnicodeAttribute
from mutagen.id3 import COMM, ID3, TXXX, USLT, WXXX, Frames, PairedTextFrame, TextFrame, UrlFrame
from mutagen._vorbis import VComment

from .tags import load_raw_tags
from .utils import seconds_to_mmss

ID3_KIND = "id3"
VORBIS_KIND = "vorbis"
ASF_KIND = "asf"

# Fields most players show first, in this order; everything else follows in file order.
STANDARD_FIELDS = (
    ("Title", {"TIT2"}, {"TITLE"}, {"Title"}),
    ("Artist", {"TPE1"}, {"ARTIST"}, {"Author"}),
    ("Album", {"TALB"}, {"ALBUM"}, {"WM/AlbumTitle"}),
    ("Album artist", {"TPE2"}, {"ALBUMARTIST", "ALBUM ARTIST"}, {"WM/AlbumArtist"}),
    ("Track number", {"TRCK"}, {"TRACKNUMBER"}, {"WM/TrackNumber", "WM/Track"}),
    ("Disc number", {"TPOS"}, {"DISCNUMBER"}, {"WM/PartOfSet"}),
    ("Date", {"TDRC", "TYER"}, {"DATE", "YEAR"}, {"WM/Year"}),
    ("Genre", {"TCON"}, {"GENRE"}, {"WM/Genre"}),
    ("Composer", {"TCOM"}, {"COMPOSER"}, {"WM/Composer"}),
    ("Comment", {"COMM"}, {"COMMENT", "DESCRIPTION"}, {"Description"}),
)
_KIND_COLUMN = {ID3_KIND: 1, VORBIS_KIND: 2, ASF_KIND: 3}

ADD_FIELD_HINTS = {
    ID3_KIND: "An ID3 frame such as TCOM, or TXXX:Name for a custom text field",
    VORBIS_KIND: "Any name, e.g. COMPOSER or MOOD",
    ASF_KIND: "Any name, e.g. WM/Composer",
}


@dataclass
class TagEntry:
    key: str
    label: str
    value: str
    editable: bool


@dataclass
class FileMetadata:
    kind: Optional[str]  # None when the file type cannot hold tags
    info: List[Tuple[str, str]]
    entries: List[TagEntry] = field(default_factory=list)

    @property
    def can_add(self) -> bool:
        return self.kind is not None


def _single_line(value: str) -> bool:
    return "\n" not in value and "\r" not in value


def _standard_rank(kind: str, key: str) -> Tuple[int, str]:
    column = _KIND_COLUMN[kind]
    base = key.split(":")[0] if kind == ID3_KIND else key
    compare = base.upper() if kind == VORBIS_KIND else base
    for index, row in enumerate(STANDARD_FIELDS):
        if compare in row[column]:
            return index, row[0]
    return len(STANDARD_FIELDS), ""


def _sorted(kind: str, entries: List[TagEntry]) -> List[TagEntry]:
    # sorted() is stable, so entries outside the standard list keep their file order.
    return sorted(entries, key=lambda entry: _standard_rank(kind, entry.key)[0])


def _id3_label(frame) -> str:
    frame_id = frame.FrameID
    _rank, label = _standard_rank(ID3_KIND, frame_id)
    if frame_id == "TXXX":
        return f"{frame.desc} (custom text)"
    if frame_id == "APIC":
        return "Picture"
    if frame_id in ("COMM", "USLT") and frame.desc:
        return f"{label or 'Lyrics'} ({frame.desc})"
    if label:
        return label
    doc = (type(frame).__doc__ or frame_id).strip().splitlines()[0]
    return doc.rstrip(".")


def _id3_entries(tags: ID3) -> List[TagEntry]:
    entries = []
    for key, frame in tags.items():
        label = _id3_label(frame)
        if isinstance(frame, PairedTextFrame):
            text = ", ".join(f"{role}: {name}" for role, name in frame.people)
            entries.append(TagEntry(key, label, text, False))
        elif isinstance(frame, TextFrame):
            for value in frame.text:
                text = str(value)
                entries.append(TagEntry(key, label, text, _single_line(text)))
        elif isinstance(frame, UrlFrame):
            entries.append(TagEntry(key, label, frame.url, True))
        elif isinstance(frame, USLT):
            entries.append(TagEntry(key, label, frame.text, _single_line(frame.text)))
        else:
            # pprint() is "KEY=description"; only the description is worth showing.
            text = frame.pprint().split("=", 1)[-1]
            entries.append(TagEntry(key, label, text, False))
    return entries


def _vorbis_label(key: str) -> str:
    _rank, label = _standard_rank(VORBIS_KIND, key)
    return label or key.replace("_", " ").capitalize()


def _vorbis_entries(tags: VComment) -> List[TagEntry]:
    return [
        TagEntry(key, _vorbis_label(key), value, _single_line(value)) for key, value in tags
    ]


def _asf_entries(tags: ASFTags) -> List[TagEntry]:
    entries = []
    for key, value in tags:
        _rank, label = _standard_rank(ASF_KIND, key)
        label = label or key.replace("WM/", "")
        text = str(value)
        editable = isinstance(value, ASFUnicodeAttribute) and _single_line(text)
        entries.append(TagEntry(key, label, text, editable))
    return entries


def _picture_entries(audio) -> List[TagEntry]:
    """FLAC keeps pictures in their own blocks rather than among the tags."""
    entries = []
    for picture in getattr(audio, "pictures", None) or []:
        size = f"{picture.width}x{picture.height}, " if picture.width else ""
        text = f"{picture.mime}, {size}{len(picture.data) // 1024} KB"
        entries.append(TagEntry("(picture)", "Picture", text, False))
    return entries


def _kind_of(tags) -> Optional[str]:
    if isinstance(tags, ID3):
        return ID3_KIND
    if isinstance(tags, VComment):
        return VORBIS_KIND
    if isinstance(tags, ASFTags):
        return ASF_KIND
    return None


def _file_kind(audio) -> Optional[str]:
    """The tag format a file has, or would get once tags are added."""
    if audio.tags is not None:
        return _kind_of(audio.tags)
    try:
        audio.add_tags()  # in memory only; nothing is saved here
    except Exception:
        return None
    return _kind_of(audio.tags)


def _file_info(path: Path, audio) -> List[Tuple[str, str]]:
    info = audio.info
    rows = [("File", str(path)), ("Format", info.pprint())]
    length = getattr(info, "length", 0)
    if length:
        rows.append(("Duration", seconds_to_mmss(length)))
    for attribute, label, unit in (
        ("bitrate", "Bitrate", "kbps"),
        ("sample_rate", "Sample rate", "Hz"),
        ("channels", "Channels", ""),
        ("bits_per_sample", "Bits per sample", ""),
    ):
        value = getattr(info, attribute, 0)
        if value:
            if attribute == "bitrate":
                value = round(value / 1000)
            rows.append((label, f"{value} {unit}".strip()))
    try:
        size = path.stat().st_size
    except OSError:
        return rows
    if size >= 1_048_576:
        rows.append(("File size", f"{size / 1_048_576:.1f} MB"))
    else:
        rows.append(("File size", f"{max(1, round(size / 1024))} KB"))
    return rows


def read_file_metadata(path: Path) -> FileMetadata:
    audio = load_raw_tags(path)
    if audio is None:
        raise ValueError("unsupported or unreadable file")
    tags = audio.tags
    kind = _kind_of(tags) if tags is not None else None
    entries: List[TagEntry] = []
    if kind == ID3_KIND:
        entries = _id3_entries(tags)
    elif kind == VORBIS_KIND:
        entries = _vorbis_entries(tags)
    elif kind == ASF_KIND:
        entries = _asf_entries(tags)
    if kind is not None:
        entries = _sorted(kind, entries)
    # A field is rewritten as a whole, so one value that cannot be edited locks its siblings.
    locked = {entry.key for entry in entries if not entry.editable}
    for entry in entries:
        if entry.key in locked:
            entry.editable = False
    entries += _picture_entries(audio)
    info = _file_info(path, audio)
    return FileMetadata(kind or _file_kind(audio), info, entries)


# ------------------------------------------------------------------ writing


def _id3_frame(key: str, values: Sequence[str]):
    frame_id, _, rest = key.partition(":")
    if frame_id == "TXXX":
        if not rest:
            raise ValueError("TXXX needs a name, e.g. TXXX:Mood")
        return TXXX(encoding=3, desc=rest, text=list(values))
    if frame_id == "COMM":
        desc, _, lang = rest.partition(":")
        return COMM(encoding=3, lang=lang or "eng", desc=desc, text=list(values))
    if frame_id == "USLT":
        desc, _, lang = rest.partition(":")
        return USLT(encoding=3, lang=lang or "eng", desc=desc, text="\n".join(values))
    if frame_id == "WXXX":
        return WXXX(encoding=3, desc=rest, url=values[0])
    frame_class = Frames.get(frame_id)
    if frame_class is not None and not rest:
        if issubclass(frame_class, TextFrame) and not issubclass(frame_class, PairedTextFrame):
            return frame_class(encoding=3, text=list(values))
        if issubclass(frame_class, UrlFrame):
            return frame_class(url=values[0])
    raise ValueError(
        f"'{key}' is not a text field MP3 tags can hold; use an ID3 frame such as TCOM, "
        "or TXXX:Name for a custom text field"
    )


def _write_id3(tags: ID3, changes: Dict[str, List[str]]) -> None:
    for key, values in changes.items():
        if not values:
            tags.delall(key)
            continue
        frame = _id3_frame(key, values)
        tags.delall(key)
        tags.add(frame)


def _write_vorbis(tags: VComment, changes: Dict[str, List[str]]) -> None:
    for key, values in changes.items():
        if not key or "=" in key or not all(" " <= char <= "}" for char in key):
            raise ValueError(f"'{key}' is not a valid field name (use ASCII letters, no '=')")
        if key in tags:
            del tags[key]
        if values:
            tags[key] = list(values)


def _write_asf(tags: ASFTags, changes: Dict[str, List[str]]) -> None:
    for key, values in changes.items():
        if not key:
            raise ValueError("field names cannot be empty")
        if key in tags:
            del tags[key]
        if values:
            tags[key] = [ASFUnicodeAttribute(value) for value in values]


_WRITERS: Dict[str, Callable] = {
    ID3_KIND: _write_id3,
    VORBIS_KIND: _write_vorbis,
    ASF_KIND: _write_asf,
}


def write_file_metadata(path: Path, changes: Dict[str, List[str]]) -> None:
    """Replace the values of each key in ``changes``; an empty list removes the field.

    Keys not in ``changes`` are left exactly as they are, including read-only ones.
    """
    if not changes:
        return
    audio = load_raw_tags(path)
    if audio is None:
        raise ValueError("unsupported or unreadable file")
    if audio.tags is None:
        try:
            audio.add_tags()
        except Exception as error:
            raise ValueError("this file type cannot hold tags") from error
    kind = _kind_of(audio.tags)
    if kind is None:
        raise ValueError("editing this tag format is not supported")
    _WRITERS[kind](audio.tags, changes)
    audio.save()


def changed_fields(
    before: Sequence[TagEntry], after: Sequence[Tuple[str, str]]
) -> Dict[str, List[str]]:
    """Per key, the new values where the editable values differ; [] means removed.

    ``after`` holds (key, value) pairs of the editable entries as edited; empty values drop.
    """
    old: Dict[str, List[str]] = {}
    for entry in before:
        if entry.editable:
            old.setdefault(entry.key, []).append(entry.value)
    new: Dict[str, List[str]] = {}
    for key, value in after:
        key = key.strip()
        if not key:
            continue
        values = new.setdefault(key, [])
        if value.strip():
            values.append(value)
    changes = {
        key: values
        for key, values in new.items()
        if old.get(key, []) != values
    }
    for key in old:
        if key not in new:
            changes[key] = []
    return changes
