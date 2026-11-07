import json

import pytest

from tag_gui.core.settings import (
    SKIP_SECONDS_DEFAULT,
    Settings,
    load_settings,
    parse_skip_seconds,
    save_settings,
)


@pytest.mark.parametrize(
    "text, previous, expected",
    [
        ("16", 5, 16),
        ("1asd6", 5, 16),
        ("07", 5, 7),
        ("60", 5, 60),
        ("", 7, SKIP_SECONDS_DEFAULT),
        ("abc", 30, SKIP_SECONDS_DEFAULT),
        ("61", 30, 30),
        ("0", 30, 30),
        ("578", 57, 57),
    ],
)
def test_skip_seconds_keeps_digits_and_ignores_out_of_range(text, previous, expected):
    assert parse_skip_seconds(text, previous) == expected


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    saved = Settings(
        skip_seconds=12, timebar_top=True, timebar_bottom=False, scrobbling_paused=True
    )
    save_settings(path, saved)
    assert load_settings(path) == saved


def test_missing_or_broken_settings_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    assert load_settings(path) == Settings()
    path.write_text("{not json", encoding="utf-8")
    assert load_settings(path) == Settings()


def test_invalid_settings_values_are_replaced(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"skip_seconds": 99, "timebar_top": False, "timebar_bottom": False}),
        encoding="utf-8",
    )
    assert load_settings(path) == Settings()
