"""Gives the Linux build an icon: a menu entry, and a custom icon on the executable file.

Linux executables cannot carry an icon the way a Windows .exe does. Menus and panels take it
from a .desktop entry, and file managers (Nemo, Nautilus, Caja) honour a per-file
``metadata::custom-icon``. The release binary is named after its version, so every start
points the entry and the file icon at the binary that is actually running.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl

from ..constants import APP_TITLE, DESKTOP_ID
from .icons import note_pixmap

ICON_SIZE = 256
GIO_TIMEOUT_SECONDS = 5


def data_home() -> Path:
    value = os.environ.get("XDG_DATA_HOME", "")
    return Path(value) if value else Path.home() / ".local" / "share"


def exec_quote(path: str) -> str:
    """Quote a path for the Exec key, as the Desktop Entry spec requires."""
    escaped = "".join("\\" + char if char in '"`$\\' else char for char in path)
    return '"' + escaped.replace("%", "%%") + '"'


def desktop_entry(executable: str, icon: Path) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_TITLE}\n"
        "Comment=Play music and edit audio file tags\n"
        f"Exec={exec_quote(executable)}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;Player;\n"
        f"StartupWMClass={DESKTOP_ID}\n"
    )


def _write_if_changed(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _png_bytes(size: int) -> bytes:
    from PySide6.QtCore import QBuffer

    buffer = QBuffer()
    buffer.open(QBuffer.WriteOnly)
    note_pixmap(size).save(buffer, "PNG")
    return bytes(buffer.data())


def system_env() -> dict:
    """The environment for system tools, without PyInstaller's bundled library path.

    The frozen app points LD_LIBRARY_PATH at its own Qt and GLib copies, which break the
    system's gio; PyInstaller keeps the original value in LD_LIBRARY_PATH_ORIG.
    """
    env = dict(os.environ)
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original is not None:
        env["LD_LIBRARY_PATH"] = original
    elif getattr(sys, "frozen", False):
        env.pop("LD_LIBRARY_PATH", None)
    return env


def set_file_icon(executable: str, icon: Path) -> None:
    """Best effort: file managers without GIO metadata simply keep their generic icon."""
    gio = shutil.which("gio")
    if not gio:
        return
    uri = QUrl.fromLocalFile(str(icon)).toString()
    try:
        subprocess.run(
            [gio, "set", executable, "metadata::custom-icon", uri],
            check=False,
            env=system_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=GIO_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def install(executable: str, base: Optional[Path] = None) -> None:
    """Write the icon and the menu entry for ``executable``, and give the file that icon."""
    base = base or data_home()
    icon = base / "icons" / "hicolor" / f"{ICON_SIZE}x{ICON_SIZE}" / "apps" / f"{DESKTOP_ID}.png"
    _write_if_changed(icon, _png_bytes(ICON_SIZE))
    entry = base / "applications" / f"{DESKTOP_ID}.desktop"
    _write_if_changed(entry, desktop_entry(executable, icon).encode("utf-8"))
    set_file_icon(executable, icon)


def integrate() -> None:
    """Called at startup; only the frozen Linux build has a stable executable to point at."""
    if not sys.platform.startswith("linux") or not getattr(sys, "frozen", False):
        return
    try:
        install(sys.executable)
    except OSError:
        pass  # A read-only home must not stop the app from starting.
