import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TXXX

from .utils import seconds_to_mmss


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


def load_easy_tags(path: Path):
    try:
        return MutagenFile(str(path), easy=True)
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


def custom_tag_checked(audio, tag_name: str) -> bool:
    # A tagless file is falsy in mutagen, so compare against None explicitly.
    if audio is None or not audio.tags:
        return False

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

    existing_key, _ = get_tag_values_case_insensitive(audio.tags, tag_name)
    if existing_key is not None:
        del audio.tags[existing_key]
    if checked:
        audio.tags[tag_name] = ["X"]
    audio.save()
