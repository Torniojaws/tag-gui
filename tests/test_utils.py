from tag_gui.core.utils import app_data_dir, seconds_to_mmss, slugify


def test_slugify_makes_an_ascii_kebab_name():
    assert slugify("Yömusa Vol. 2") == "yomusa-vol-2"


def test_slugify_collapses_runs_and_trims_separators():
    assert slugify("  --Rock & Roll--  ") == "rock-roll"


def test_slugify_falls_back_when_nothing_survives():
    assert slugify("///") == "playlist"
    assert slugify("") == "playlist"


def test_seconds_to_mmss_pads_both_parts():
    assert seconds_to_mmss(0) == "00:00"
    assert seconds_to_mmss(9) == "00:09"
    assert seconds_to_mmss(61) == "01:01"


def test_seconds_to_mmss_truncates_and_passes_the_hour():
    assert seconds_to_mmss(59.9) == "00:59"
    assert seconds_to_mmss(3600) == "60:00"


def test_seconds_to_mmss_treats_missing_length_as_zero():
    assert seconds_to_mmss(None) == "00:00"


def test_app_data_dir_exists_after_the_call(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    path = app_data_dir()
    assert path.is_dir()
    assert path.name == "tag-gui"
