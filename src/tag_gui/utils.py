import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Callable, Iterable, List, Optional

from .constants import AUDIO_EXTENSIONS


def slugify(name: str) -> str:
    """ASCII kebab-case file name, so playlists keep working on any filesystem."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(char for char in decomposed if not unicodedata.combining(char))
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "playlist"


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


def collect_audio_files(
    paths: Iterable[str],
    on_progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> List[str]:
    """Expand dropped paths into audio files, walking directories recursively."""
    found: List[str] = []

    def take(path: Path) -> None:
        found.append(str(path))
        if on_progress:
            on_progress(len(found))

    for raw in paths:
        p = Path(raw)
        if p.is_file():
            if p.suffix.lower() in AUDIO_EXTENSIONS:
                take(p)
            continue
        for dir_path, dir_names, file_names in os.walk(p):
            if should_cancel and should_cancel():
                return found
            dir_names.sort()
            for name in sorted(file_names):
                if Path(name).suffix.lower() in AUDIO_EXTENSIONS:
                    take(Path(dir_path) / name)
    return found
