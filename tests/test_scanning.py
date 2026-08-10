from pathlib import Path

from tag_gui.core.scanning import collect_audio_files


def make_tree(root):
    (root / "music" / "album").mkdir(parents=True)
    (root / "music" / "a.mp3").touch()
    (root / "music" / "cover.jpg").touch()
    (root / "music" / "album" / "b.FLAC").touch()
    (root / "music" / "album" / "notes.txt").touch()
    return root / "music"


def test_keeps_only_audio_extensions(tmp_path):
    music = make_tree(tmp_path)
    found = collect_audio_files([str(music)])
    assert [Path(p).name for p in found] == ["a.mp3", "b.FLAC"]


def test_walks_directories_recursively(tmp_path):
    music = make_tree(tmp_path)
    assert any("album" in path for path in collect_audio_files([str(music)]))


def test_accepts_files_directly(tmp_path):
    music = make_tree(tmp_path)
    found = collect_audio_files([str(music / "a.mp3"), str(music / "cover.jpg")])
    assert len(found) == 1


def test_ignores_paths_that_do_not_exist(tmp_path):
    assert collect_audio_files([str(tmp_path / "missing")]) == []


def test_reports_progress_for_every_file(tmp_path):
    music = make_tree(tmp_path)
    counts = []
    collect_audio_files([str(music)], on_progress=counts.append)
    assert counts == [1, 2]


def test_cancelling_stops_the_walk(tmp_path):
    music = make_tree(tmp_path)
    found = collect_audio_files([str(music)], should_cancel=lambda: True)
    assert found == []
