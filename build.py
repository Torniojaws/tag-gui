#!/usr/bin/env python3
"""Build tasks for tag-gui: python build.py [deps] [test] [icon] [build] [glibc] [run] [clean]"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = "tag-gui"
ICON = ROOT / f"{APP}.ico"
ICON_SOURCES = ("make_icon.py", "app.py", "src/tag_gui/ui/icons.py", "src/tag_gui/constants.py")
WINDOWS = sys.platform == "win32"
EXE = ROOT / "dist" / (f"{APP}.exe" if WINDOWS else APP)

# Prefer the project venv so the result does not depend on which shell is activated.
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# The newest glibc symbol version the Linux build may need. The release build is made on
# AlmaLinux 9: its glibc is 2.34 but has 2.35 symbols backported, and its libgcc_s needs one of
# them (_dl_find_object@GLIBC_2.35). That still runs on RHEL 9 and on any upstream glibc 2.35+
# (Ubuntu 22.04, Debian 12); only a plain upstream 2.34, such as the long-dead Fedora 35, misses it.
GLIBC_FLOOR = (2, 35)


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def deps() -> None:
    run(PYTHON, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller", "pytest")


def test() -> None:
    run(PYTHON, "-m", "pytest")


def icon() -> None:
    newest_source = max((ROOT / name).stat().st_mtime for name in ICON_SOURCES)
    if ICON.exists() and ICON.stat().st_mtime >= newest_source:
        print(f"{ICON.name} is up to date")
        return
    run(PYTHON, "make_icon.py")


def build() -> None:
    if WINDOWS:
        icon()
    if EXE.exists():
        try:
            EXE.unlink()
        except PermissionError:
            # Windows locks a running executable, and PyInstaller only fails once it is done.
            raise SystemExit(f"{EXE} is in use - close the running app and build again")
    args = [
        PYTHON, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--paths", "src",
    ]
    if WINDOWS:
        # PyInstaller only embeds an .ico into the executable on Windows.
        args += ["--icon", ICON.name]
    if (ROOT / "src" / "tag_gui" / "_lastfm_keys.py").exists():
        # Imported lazily and optionally, so make sure PyInstaller bundles it.
        args += ["--hidden-import", "tag_gui._lastfm_keys"]
    args += ["--name", APP, "app.py"]
    run(*args)


def glibc() -> None:
    """Fail if anything bundled into the Linux executable needs a glibc newer than GLIBC_FLOOR."""
    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        if PYTHON == sys.executable:
            raise
        run(PYTHON, __file__, "glibc")
        return

    pattern = re.compile(rb"GLIBC_(\d+)\.(\d+)")
    newest: dict[tuple[int, int], list[str]] = {}

    def scan(name: str, data: bytes) -> None:
        if not data.startswith(b"\x7fELF"):
            return
        for match in pattern.finditer(data):
            version = (int(match[1]), int(match[2]))
            users = newest.setdefault(version, [])
            if name not in users:
                users.append(name)

    scan(EXE.name, EXE.read_bytes())
    archive = CArchiveReader(str(EXE))
    for name in archive.toc:
        scan(name, archive.extract(name))

    highest = max(newest)
    print(f"{EXE.name} needs glibc {highest[0]}.{highest[1]}")
    too_new = sorted(version for version in newest if version > GLIBC_FLOOR)
    if too_new:
        for version in too_new:
            print(f"  GLIBC_{version[0]}.{version[1]}: {', '.join(newest[version])}", file=sys.stderr)
        floor = ".".join(map(str, GLIBC_FLOOR))
        raise SystemExit(f"the executable must run on glibc {floor}: build it on an older system")


def run_app() -> None:
    run(str(EXE))


def clean() -> None:
    for path in (ROOT / "build", ROOT / "dist"):
        shutil.rmtree(path, ignore_errors=True)
    (ROOT / f"{APP}.spec").unlink(missing_ok=True)
    print("removed build artifacts")


TASKS = {
    "deps": deps,
    "test": test,
    "icon": icon,
    "build": build,
    "glibc": glibc,
    "run": run_app,
    "clean": clean,
}


def main(argv: list[str]) -> int:
    tasks = argv or ["build"]
    unknown = [name for name in tasks if name not in TASKS]
    if unknown:
        print(f"unknown task: {', '.join(unknown)}", file=sys.stderr)
        print(f"available: {', '.join(TASKS)}", file=sys.stderr)
        return 2
    try:
        for name in tasks:
            TASKS[name]()
    except subprocess.CalledProcessError as error:
        print(f"task failed with exit code {error.returncode}", file=sys.stderr)
        return error.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
