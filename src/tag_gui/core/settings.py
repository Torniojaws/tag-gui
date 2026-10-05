import json
from dataclasses import asdict, dataclass
from pathlib import Path

SKIP_SECONDS_DEFAULT = 5
SKIP_SECONDS_MIN = 1
SKIP_SECONDS_MAX = 60


@dataclass
class Settings:
    skip_seconds: int = SKIP_SECONDS_DEFAULT
    timebar_top: bool = False
    timebar_bottom: bool = True


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
    return settings


def save_settings(path: Path, settings: Settings) -> None:
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
