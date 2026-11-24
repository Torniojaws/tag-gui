import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from mutagen import File as MutagenFile
from mutagen._util import DictMixin
from mutagen.aiff import AIFF
from mutagen.apev2 import APETextValue
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TXXX
from mutagen.monkeysaudio import MonkeysAudio
from mutagen.mp4 import AtomDataType, MP4FreeForm, MP4Tags
from mutagen.wavpack import WavPack

from .utils import seconds_to_mmss

# Prefix of the freeform atoms iTunes and most taggers use for custom MP4 text fields.
MP4_CUSTOM_PREFIX = "----:com.apple.iTunes:"


def parse_custom_tags(text: str) -> List[str]:
    tags = []
    seen = set()
    for part in text.split(","):
        t = unicodedata.normalize("NFC", part.strip())
        key = normalize_tag_name(t)
        if t and key not in seen:
            seen.add(key)
            tags.append(t)
    return tags


def ascii_tag_key(name: str) -> str:
    """Tag names are shown as typed but stored as ASCII, so "Yömusa" is written as "Yomusa"."""
    key = []
    for char in unicodedata.normalize("NFKD", str(name).strip()):
        if unicodedata.combining(char):
            continue
        key.append(char if " " <= char <= "}" and char != "=" else "_")
    return "".join(key)


def normalize_tag_name(name: str) -> str:
    return ascii_tag_key(name).casefold()


class _EasyIFFID3(EasyID3):
    """EasyID3 over the ID3 chunk of an AIFF file, which mutagen only offers as raw ID3."""

    def __init__(self, id3):
        self._EasyID3__id3 = id3  # where EasyID3 keeps the tags it wraps

    def save(self, filething=None, **kwargs):
        kwargs.pop("v1", None)  # an IFF chunk has no ID3v1 footer
        self._EasyID3__id3.save(filething, **kwargs)


class _EasyAIFF(AIFF):
    def load(self, filething, **kwargs):
        super().load(filething, **kwargs)
        if self.tags is not None:
            self.tags = _EasyIFFID3(self.tags)

    def add_tags(self):
        super().add_tags()
        self.tags = _EasyIFFID3(self.tags)


# APEv2 keys are case-insensitive; mapping every standard field writes the usual spelling.
_APE_KEYS = {
    "title": "Title",
    "artist": "Artist",
    "album": "Album",
    "genre": "Genre",
    "date": "Year",
    "albumartist": "Album Artist",
    "tracknumber": "Track",
    "discnumber": "Disc",
}


class _EasyAPEv2(DictMixin):
    """Easy-tag names over APEv2 tags, which call some standard fields differently."""

    def __init__(self, tags):
        self._tags = tags

    @staticmethod
    def _key(key: str) -> str:
        return _APE_KEYS.get(key.lower(), key)

    def __getitem__(self, key):
        value = self._tags[self._key(key)]
        return list(value) if isinstance(value, APETextValue) else [str(value)]

    def __setitem__(self, key, values):
        self._tags[self._key(key)] = list(values)

    def __delitem__(self, key):
        del self._tags[self._key(key)]

    def keys(self):
        return list(self._tags.keys())

    def save(self, filething=None, **kwargs):
        self._tags.save(filething, **kwargs)


class _EasyAPEv2Mixin:
    def load(self, filething, **kwargs):
        super().load(filething, **kwargs)
        if self.tags is not None:
            self.tags = _EasyAPEv2(self.tags)

    def add_tags(self):
        super().add_tags()
        self.tags = _EasyAPEv2(self.tags)


class _EasyWavPack(_EasyAPEv2Mixin, WavPack):
    pass


class _EasyMonkeysAudio(_EasyAPEv2Mixin, MonkeysAudio):
    pass


# Formats mutagen has no easy-tag view for, opened again through one of ours.
_EASY_TYPES = {AIFF: _EasyAIFF, WavPack: _EasyWavPack, MonkeysAudio: _EasyMonkeysAudio}


def load_easy_tags(path: Path):
    try:
        audio = MutagenFile(str(path), easy=True)
        easy_type = _EASY_TYPES.get(type(audio))
        return easy_type(str(path)) if easy_type else audio
    except Exception:
        return None


def load_raw_tags(path: Path):
    try:
        return MutagenFile(str(path), easy=False)
    except Exception:
        return None


def get_field(tags, key: str) -> str:
    if not tags:
        return ""
    values = tags.get(key)
    if not values:
        return ""
    value = values[0]
    return str(value)


def get_duration(path: Path) -> str:
    audio = load_raw_tags(path)
    if audio is None or not getattr(audio, "info", None):
        return "00:00"
    return seconds_to_mmss(getattr(audio.info, "length", 0))


def _leading_number(value: str) -> int:
    """``"3/12"`` -> 3; anything without a leading number -> 0, meaning not set."""
    digits = ""
    for char in value.strip():
        if not char.isdigit():
            break
        digits += char
    return int(digits) if digits else 0


def read_track_position(path: Path) -> Tuple[int, int]:
    return position_from_tags(load_easy_tags(path))


def position_from_tags(easy) -> Tuple[int, int]:
    """(disc number, track number), each 0 when the tag is missing."""
    if not easy:
        return 0, 0
    return (
        _leading_number(get_field(easy, "discnumber")),
        _leading_number(get_field(easy, "tracknumber")),
    )


def get_tag_values_case_insensitive(tags, target: str):
    target_n = normalize_tag_name(target)
    for key, values in tags.items():
        if normalize_tag_name(str(key)) == target_n:
            return key, values
    return None, None


def _mp4_custom_keys(tags: MP4Tags, tag_name: str) -> List[str]:
    target = normalize_tag_name(tag_name)
    return [
        key
        for key in tags.keys()
        if key.startswith(MP4_CUSTOM_PREFIX)
        and normalize_tag_name(key[len(MP4_CUSTOM_PREFIX):]) == target
    ]


def custom_tag_checked(audio, tag_name: str) -> bool:
    # A tagless file is falsy in mutagen, so compare against None explicitly.
    if audio is None or not audio.tags:
        return False

    if isinstance(audio.tags, MP4Tags):
        return any(
            bytes(value) == b"X"
            for key in _mp4_custom_keys(audio.tags, tag_name)
            for value in audio.tags[key]
        )

    if isinstance(audio.tags, ID3):
        for frame in audio.tags.getall("TXXX"):
            if normalize_tag_name(frame.desc) == normalize_tag_name(tag_name):
                values = [str(v) for v in frame.text]
                if any(v == "X" for v in values):
                    return True
        return False

    key, values = get_tag_values_case_insensitive(audio.tags, tag_name)
    if not key or not values:
        return False
    return any(str(v) == "X" for v in values)


def read_custom_tag_states(path: Path, tag_names: Iterable[str]) -> Dict[str, bool]:
    """Read every custom tag of a file from one open, instead of one open per tag."""
    audio = load_raw_tags(path)
    return {tag: custom_tag_checked(audio, tag) for tag in tag_names}


def set_standard_tags(path: Path, values: Dict[str, str]) -> None:
    """Write only the given easy-tag keys, leaving every other tag untouched."""
    audio = load_easy_tags(path)
    if audio is None:
        raise ValueError("unsupported or unreadable file")
    if audio.tags is None:
        audio.add_tags()
    for key, value in values.items():
        if value:
            audio[key] = [value]
        elif key in audio:
            del audio[key]
    audio.save()


def set_custom_tag(path: Path, tag_name: str, checked: bool):
    audio = load_raw_tags(path)
    if audio is None:
        return

    tag_name = ascii_tag_key(tag_name)

    if audio.tags is None:
        audio.add_tags()

    if isinstance(audio.tags, ID3):
        for frame in list(audio.tags.getall("TXXX")):
            if normalize_tag_name(frame.desc) == normalize_tag_name(tag_name):
                audio.tags.delall(f"TXXX:{frame.desc}")
        if checked:
            audio.tags.add(TXXX(encoding=3, desc=tag_name, text=["X"]))
        audio.save()
        return

    if isinstance(audio.tags, MP4Tags):
        for key in _mp4_custom_keys(audio.tags, tag_name):
            del audio.tags[key]
        if checked:
            audio.tags[MP4_CUSTOM_PREFIX + tag_name] = [
                MP4FreeForm(b"X", dataformat=AtomDataType.UTF8)
            ]
        audio.save()
        return

    existing_key, _ = get_tag_values_case_insensitive(audio.tags, tag_name)
    if existing_key is not None:
        del audio.tags[existing_key]
    if checked:
        audio.tags[tag_name] = ["X"]
    audio.save()
