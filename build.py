#!/usr/bin/env python3
"""Build tasks for tag-gui: python build.py [deps] [icon] [build] [run] [clean]"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = "tag-gui"
ICON = ROOT / f"{APP}.ico"
ICON_SOURCES = ("make_icon.py", "app.py", "src/tag_gui/icons.py", "src/tag_gui/constants.py")
WINDOWS = sys.platform == "win32"
EXE = ROOT / "dist" / (f"{APP}.exe" if WINDOWS else APP)

# Prefer the project venv so the result does not depend on which shell is activated.
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def run(*args: str) -> None:
    print("+", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


def deps() -> None:
    run(PYTHON, "-m", "pip", "install", "-r", "requirements.txt", "pyinstaller")


def icon() -> None:
    newest_source = max((ROOT / name).stat().st_mtime for name in ICON_SOURCES)
    if ICON.exists() and ICON.stat().st_mtime >= newest_source:
        print(f"{ICON.name} is up to date")
        return
    run(PYTHON, "make_icon.py")


def build() -> None:
    icon()
    run(
        PYTHON, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--paths", "src",
        "--icon", ICON.name, "--name", APP, "app.py",
    )


def run_app() -> None:
    run(str(EXE))


def clean() -> None:
    for path in (ROOT / "build", ROOT / "dist"):
        shutil.rmtree(path, ignore_errors=True)
    (ROOT / f"{APP}.spec").unlink(missing_ok=True)
    print("removed build artifacts")


TASKS = {"deps": deps, "icon": icon, "build": build, "run": run_app, "clean": clean}


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
