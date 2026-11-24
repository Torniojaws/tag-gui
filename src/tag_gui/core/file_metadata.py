"""Every tag of a file, in a standard order, plus writing edited tags back.

Tags are shown one value per entry, so a field with two artists becomes two entries with the
same key and nothing is lost by joining and splitting values. Text values can be edited;
pictures, binary frames and multi-line text are shown read-only.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from mutagen.apev2 import APEBinaryValue, APEv2, APETextValue, is_valid_apev2_key
from mutagen.asf import ASFTags, ASFUnicodeAttribute
from mutagen.id3 import COMM, ID3, TXXX, USLT, WXXX, Frames, PairedTextFrame, TextFrame, UrlFrame
from mutagen.mp4 import AtomDataType, MP4Cover, MP4FreeForm, MP4Tags
from mutagen._vorbis import VComment

from .tags import MP4_CUSTOM_PREFIX, load_raw_tags
from .utils import seconds_to_mmss

ID3_KIND = "id3"
VORBIS_KIND = "vorbis"
ASF_KIND = "asf"
MP4_KIND = "mp4"
APE_KIND = "ape"

# Fields most players show first, in this order; everything else follows in file order.
# Columns: label, then the keys in ID3, Vorbis, ASF, MP4 and APEv2 tags.
STANDARD_FIELDS = (
    ("Title", {"TIT2"}, {"TITLE"}, {"Title"}, {"©nam"}, {"TITLE"}),
    ("Artist", {"TPE1"}, {"ARTIST"}, {"Author"}, {"©ART"}, {"ARTIST"}),
    ("Album", {"TALB"}, {"ALBUM"}, {"WM/AlbumTitle"}, {"©alb"}, {"ALBUM"}),
    (
        "Album artist",
        {"TPE2"},
        {"ALBUMARTIST", "ALBUM ARTIST"},
        {"WM/AlbumArtist"},
        {"aART"},
        {"ALBUM ARTIST", "ALBUMARTIST"},
    ),
    ("Track number", {"TRCK"}, {"TRACKNUMBER"}, {"WM/TrackNumber", "WM/Track"}, {"trkn"}, {"TRACK"}),
    ("Disc number", {"TPOS"}, {"DISCNUMBER"}, {"WM/PartOfSet"}, {"disk"}, {"DISC"}),
    ("Date", {"TDRC", "TYER"}, {"DATE", "YEAR"}, {"WM/Year"}, {"©day"}, {"YEAR"}),
    ("Genre", {"TCON"}, {"GENRE"}, {"WM/Genre"}, {"©gen", "gnre"}, {"GENRE"}),
    ("Composer", {"TCOM"}, {"COMPOSER"}, {"WM/Composer"}, {"©wrt"}, {"COMPOSER"}),
    ("Comment", {"COMM"}, {"COMMENT", "DESCRIPTION"}, {"Description"}, {"©cmt"}, {"COMMENT"}),
)
_KIND_COLUMN = {ID3_KIND: 1, VORBIS_KIND: 2, ASF_KIND: 3, MP4_KIND: 4, APE_KIND: 5}
# Tag formats whose keys are case-insensitive; their STANDARD_FIELDS keys are upper case.
_CASELESS_KINDS = (VORBIS_KIND, APE_KIND)

ADD_FIELD_HINTS = {
    ID3_KIND: "An ID3 frame such as TCOM, or TXXX:Name for a custom text field",
    VORBIS_KIND: "Any name, e.g. COMPOSER or MOOD",
    ASF_KIND: "Any name, e.g. WM/Composer",
    MP4_KIND: f"An atom such as ©wrt, or {MP4_CUSTOM_PREFIX}Name for a custom text field",
    APE_KIND: "Any name, e.g. Composer or Mood",
}

# MP4 atoms outside STANDARD_FIELDS that have a well-known meaning.
_MP4_LABELS = {
    "©too": "Encoder",
    "©lyr": "Lyrics",
    "©grp": "Grouping",
    "cpil": "Compilation",
    "tmpo": "BPM",
    "desc": "Description",
    "cprt": "Copyright",
}
# Atoms holding (number, total) pairs, shown and edited as "3/12".
_MP4_PAIR_ATOMS = ("trkn", "disk")
# Text atoms whose names do not start with ©; those starting with © are all text.
_MP4_TEXT_ATOMS = {
    "aART", "desc", "ldes", "cprt", "soar", "soal", "soaa", "sonm", "soco", "sosn", "tvsh",
    "purl", "egid", "catg", "keyw",
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
    compare = base.upper() if kind in _CASELESS_KINDS else base
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


def _mp4_label(key: str) -> str:
    _rank, label = _standard_rank(MP4_KIND, key)
    if label:
        return label
    if key == "covr":
        return "Picture"
    if key.startswith("----:"):
        return f"{key.rsplit(':', 1)[-1]} (custom text)"
    return _MP4_LABELS.get(key, key)


def _mp4_text(value) -> Tuple[str, bool]:
    """How an MP4 value is shown, and whether it can be edited as text."""
    if isinstance(value, MP4Cover):
        image = "PNG" if value.imageformat == MP4Cover.FORMAT_PNG else "JPEG"
        return f"{image} image, {len(value) // 1024} KB", False
    if isinstance(value, MP4FreeForm):
        try:
            text = bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            return f"{len(value)} bytes of binary data", False
        return text, _single_line(text)
    if isinstance(value, tuple):
        number, total = (tuple(value) + (0, 0))[:2]
        return (f"{number}/{total}" if total else str(number)), True
    if isinstance(value, str):
        return value, _single_line(value)
    return str(value), False


def _mp4_entries(tags: MP4Tags) -> List[TagEntry]:
    entries = []
    for key, values in tags.items():
        label = _mp4_label(key)
        for value in values if isinstance(values, list) else [values]:
            text, editable = _mp4_text(value)
            entries.append(TagEntry(key, label, text, editable))
    return entries


def _ape_entries(tags: APEv2) -> List[TagEntry]:
    entries = []
    for key, value in tags.items():
        _rank, label = _standard_rank(APE_KIND, key)
        label = label or key
        if isinstance(value, APETextValue):
            for text in value:
                entries.append(TagEntry(key, label, text, _single_line(text)))
        elif isinstance(value, APEBinaryValue):
            if key.lower().startswith("cover art"):
                label = "Picture"
            entries.append(TagEntry(key, label, f"{len(value.value) // 1024} KB of data", False))
        else:
            entries.append(TagEntry(key, label, str(value), False))
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
    if isinstance(tags, MP4Tags):
        return MP4_KIND
    if isinstance(tags, APEv2):
        return APE_KIND
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
    elif kind == MP4_KIND:
        entries = _mp4_entries(tags)
    elif kind == APE_KIND:
        entries = _ape_entries(tags)
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


def _mp4_pair(text: str) -> Tuple[int, int]:
    number, _, total = text.partition("/")
    try:
        return int(number), int(total) if total.strip() else 0
    except ValueError:
        raise ValueError(f"'{text}' is not a number such as 3 or 3/12") from None


def _mp4_values(key: str, values: Sequence[str]) -> list:
    if key.startswith("----:"):
        _prefix, mean, name = (key.split(":", 2) + ["", ""])[:3]
        if not mean or not name:
            raise ValueError(f"'{key}' needs a name, e.g. {MP4_CUSTOM_PREFIX}Mood")
        return [MP4FreeForm(value.encode("utf-8"), dataformat=AtomDataType.UTF8) for value in values]
    if key in _MP4_PAIR_ATOMS:
        return [_mp4_pair(value) for value in values]
    if (len(key) == 4 and key.startswith("©")) or key in _MP4_TEXT_ATOMS:
        return list(values)
    raise ValueError(
        f"'{key}' is not a text field M4A tags can hold; use an atom such as ©wrt, "
        f"or {MP4_CUSTOM_PREFIX}Name for a custom text field"
    )


def _write_mp4(tags: MP4Tags, changes: Dict[str, List[str]]) -> None:
    for key, values in changes.items():
        if not values:
            tags.pop(key, None)
            continue
        tags[key] = _mp4_values(key, values)


def _write_ape(tags: APEv2, changes: Dict[str, List[str]]) -> None:
    for key, values in changes.items():
        if not is_valid_apev2_key(key):
            raise ValueError(f"'{key}' is not a valid field name (2 to 255 ASCII characters)")
        if key in tags:
            del tags[key]
        if values:
            tags[key] = list(values)


_WRITERS: Dict[str, Callable] = {
    ID3_KIND: _write_id3,
    VORBIS_KIND: _write_vorbis,
    ASF_KIND: _write_asf,
    MP4_KIND: _write_mp4,
    APE_KIND: _write_ape,
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
