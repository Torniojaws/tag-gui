import os
import re
import sys
import unicodedata
from pathlib import Path


def app_data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    path = base / "tag-gui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def seconds_to_mmss(seconds: float) -> str:
    total = int(seconds or 0)
    return f"{total // 60:02d}:{total % 60:02d}"


def slugify(name: str) -> str:
    """ASCII kebab-case file name, so playlists keep working on any filesystem."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "playlist"
