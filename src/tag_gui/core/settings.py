import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List

SKIP_SECONDS_DEFAULT = 5
SKIP_SECONDS_MIN = 1
SKIP_SECONDS_MAX = 60


@dataclass
class Settings:
    skip_seconds: int = SKIP_SECONDS_DEFAULT
    timebar_top: bool = False
    timebar_bottom: bool = True
    shuffle: bool = False
    scrobbling_paused: bool = False
    # Playlist columns by header name, shared by every playlist. An empty order means the
    # default; columns without a stored width are sized to their contents.
    column_order: List[str] = field(default_factory=list)
    column_widths: Dict[str, int] = field(default_factory=dict)


def parse_skip_seconds(text: str, previous: int) -> int:
    """Digits are kept and everything else dropped; an out-of-range number keeps `previous`."""
    digits = "".join(ch for ch in text if ch in "0123456789")
    if not digits:
        return SKIP_SECONDS_DEFAULT
    value = int(digits)
    return value if SKIP_SECONDS_MIN <= value <= SKIP_SECONDS_MAX else previous


def load_settings(path: Path) -> Settings:
    settings = Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if not isinstance(data, dict):
        return settings

    skip = data.get("skip_seconds")
    if isinstance(skip, int) and SKIP_SECONDS_MIN <= skip <= SKIP_SECONDS_MAX:
        settings.skip_seconds = skip
    top, bottom = data.get("timebar_top"), data.get("timebar_bottom")
    if isinstance(top, bool) and isinstance(bottom, bool) and (top or bottom):
        settings.timebar_top, settings.timebar_bottom = top, bottom
    if isinstance(data.get("shuffle"), bool):
        settings.shuffle = data["shuffle"]
    if isinstance(data.get("scrobbling_paused"), bool):
        settings.scrobbling_paused = data["scrobbling_paused"]
    order = data.get("column_order")
    if isinstance(order, list):
        names = [name for name in order if isinstance(name, str)]
        settings.column_order = list(dict.fromkeys(names))
    widths = data.get("column_widths")
    if isinstance(widths, dict):
        settings.column_widths = {
            name: width
            for name, width in widths.items()
            if isinstance(width, int) and not isinstance(width, bool) and width > 0
        }
    return settings


def save_settings(path: Path, settings: Settings) -> None:
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
