from tag_gui.core import copying
from tag_gui.core.copying import copy_files, total_bytes


def make_sources(root, sizes=(10, 20)):
    source = root / "source"
    source.mkdir()
    paths = []
    for index, size in enumerate(sizes):
        path = source / f"song{index}.flac"
        path.write_bytes(bytes([index]) * size)
        paths.append(str(path))
    return paths


def test_copies_files_and_keeps_originals(tmp_path):
    paths = make_sources(tmp_path)
    target = tmp_path / "target"
    result = copy_files(paths, str(target))

    assert sorted(p.name for p in target.iterdir()) == ["song0.flac", "song1.flac"]
    assert (target / "song1.flac").read_bytes() == bytes([1]) * 20
    assert all((tmp_path / "source" / name).exists() for name in ("song0.flac", "song1.flac"))
    assert len(result.copied) == 2 and not result.cancelled


def test_reports_running_byte_totals(tmp_path):
    paths = make_sources(tmp_path)
    reported = []
    copy_files(paths, str(tmp_path / "target"), on_progress=reported.append)
    assert reported[-1] == total_bytes(paths) == 30
    assert reported == sorted(reported)


def test_skips_existing_copies_and_renames_clashes(tmp_path):
    paths = make_sources(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (target / "song0.flac").write_bytes(bytes([0]) * 10)
    (target / "song1.flac").write_bytes(b"different")

    result = copy_files(paths, str(target))

    assert result.skipped == [paths[0]]
    assert (target / "song1.flac").read_bytes() == b"different"
    assert (target / "song1 (2).flac").read_bytes() == bytes([1]) * 20


def test_missing_sources_are_reported(tmp_path):
    result = copy_files([str(tmp_path / "gone.flac")], str(tmp_path / "target"))
    assert result.missing == [str(tmp_path / "gone.flac")]
    assert result.copied == []


def test_cancelling_mid_file_removes_the_partial_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(copying, "CHUNK_SIZE", 4)
    paths = make_sources(tmp_path)
    target = tmp_path / "target"
    result = copy_files(paths, str(target), should_cancel=lambda: True)

    assert result.cancelled
    assert result.copied == []
    assert list(target.iterdir()) == []
