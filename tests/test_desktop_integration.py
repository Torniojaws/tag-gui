import subprocess
import sys

from tag_gui.ui import desktop_integration as di


def test_exec_paths_are_quoted_per_the_desktop_entry_spec():
    assert di.exec_quote("/opt/tag gui/app") == '"/opt/tag gui/app"'
    assert di.exec_quote('/a"b$c`d\\e%f') == '"/a\\"b\\$c\\`d\\\\e%%f"'


def test_install_writes_the_icon_and_menu_entry_once(qapp, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(di.shutil, "which", lambda name: "/usr/bin/gio")
    monkeypatch.setattr(di.subprocess, "run", lambda args, **kwargs: calls.append(args))
    # Only a string here, so it is a Linux path on every OS the suite runs on.
    binary = "/home/user/Downloads/tag-gui-v1.3.1-linux-x86_64"

    di.install(binary, tmp_path)

    icon = tmp_path / "icons/hicolor/256x256/apps/tag-gui.png"
    entry = tmp_path / "applications/tag-gui.desktop"
    assert icon.read_bytes().startswith(b"\x89PNG")
    text = entry.read_text(encoding="utf-8")
    assert f'Exec="{binary}"' in text
    assert f"Icon={icon}" in text
    assert "StartupWMClass=tag-gui" in text
    assert calls == [
        ["/usr/bin/gio", "set", binary, "metadata::custom-icon", icon.as_uri()]
    ]

    # Unchanged files are left alone; a new version only rewrites the entry.
    icon_time, entry_time = icon.stat().st_mtime_ns, entry.stat().st_mtime_ns
    di.install(binary, tmp_path)
    assert (icon.stat().st_mtime_ns, entry.stat().st_mtime_ns) == (icon_time, entry_time)
    newer = binary.replace("1.3.1", "1.4.0")
    di.install(newer, tmp_path)
    assert f'Exec="{newer}"' in entry.read_text(encoding="utf-8")
    assert icon.stat().st_mtime_ns == icon_time


def test_missing_gio_or_a_failing_gio_is_ignored(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(di.shutil, "which", lambda name: None)
    di.install(str(tmp_path / "app"), tmp_path)

    def broken(*args, **kwargs):
        raise subprocess.TimeoutExpired("gio", 5)

    monkeypatch.setattr(di.shutil, "which", lambda name: "/usr/bin/gio")
    monkeypatch.setattr(di.subprocess, "run", broken)
    di.install(str(tmp_path / "app"), tmp_path)


def test_integrate_only_runs_for_the_frozen_linux_build(monkeypatch):
    installed = []
    monkeypatch.setattr(di, "install", lambda executable: installed.append(executable))
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delattr(sys, "frozen", raising=False)
    di.integrate()
    assert installed == []

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    di.integrate()
    assert installed == [sys.executable]

    monkeypatch.setattr(sys, "platform", "win32")
    di.integrate()
    assert installed == [sys.executable]


def test_gio_runs_with_the_system_library_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI123")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/local/lib")
    env = di.system_env()
    assert env["LD_LIBRARY_PATH"] == "/usr/local/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in env

    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    assert "LD_LIBRARY_PATH" not in di.system_env()
