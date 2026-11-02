"""Copying playlist tracks into another directory, leaving the originals untouched."""

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, List, Optional

CHUNK_SIZE = 1024 * 1024


@dataclass
class CopyResult:
    copied: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    cancelled: bool = False


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def total_bytes(paths: Iterable[str]) -> int:
    return sum(_file_size(Path(p)) for p in paths)


def _destination(source: Path, target_dir: Path) -> Optional[Path]:
    """Where to copy ``source``, or None when an identical-sized copy is already there.

    A same-named file of another size is never overwritten; the copy gets a numbered name.
    """
    candidate = target_dir / source.name
    if not candidate.exists():
        return candidate
    if candidate.stat().st_size == source.stat().st_size:
        return None
    number = 2
    while True:
        candidate = target_dir / f"{source.stem} ({number}){source.suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def copy_files(
    paths: Iterable[str],
    target_dir: str,
    on_progress: Optional[Callable[[int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> CopyResult:
    """Copy files into ``target_dir``, reporting the running total of bytes handled."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    result = CopyResult()
    done = 0

    def advance(amount: int) -> None:
        nonlocal done
        done += amount
        if on_progress:
            on_progress(done)

    for raw in paths:
        if should_cancel and should_cancel():
            result.cancelled = True
            break
        source = Path(raw)
        if not source.is_file():
            result.missing.append(raw)
            continue
        destination = _destination(source, target)
        if destination is None:
            result.skipped.append(raw)
            advance(_file_size(source))
            continue
        try:
            cancelled = _copy_one(source, destination, advance, should_cancel)
        except OSError:
            result.failed.append(raw)
            continue
        if cancelled:
            result.cancelled = True
            break
        result.copied.append(str(destination))
    return result


def _copy_one(
    source: Path,
    destination: Path,
    advance: Callable[[int], None],
    should_cancel: Optional[Callable[[], bool]],
) -> bool:
    """Copy in chunks so big files still move the progress bar. Returns True if cancelled."""
    complete = False
    with source.open("rb") as src, destination.open("xb") as dst:
        try:
            while chunk := src.read(CHUNK_SIZE):
                dst.write(chunk)
                advance(len(chunk))
                if should_cancel and should_cancel():
                    break
            else:
                complete = True
        finally:
            if not complete:
                # Never leave a half-written file behind, whether cancelled or failed.
                dst.close()
                destination.unlink(missing_ok=True)
    if not complete:
        return True
    try:
        shutil.copystat(source, destination)
    except OSError:
        pass  # Some targets (e.g. FAT USB sticks) reject permission bits; the data is copied.
    return False
