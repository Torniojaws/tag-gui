"""Colours, glyphs and sizes. Kept apart from constants.py, which holds data rules."""

# Title bar state markers.
PLAY_GLYPH = "\u25b6"
PAUSE_GLYPH = "\u23f8"

# Geometric shapes render in the default UI font, unlike the media control emoji.
PREV_BUTTON_GLYPH = "\u25c0\u25c0"
NEXT_BUTTON_GLYPH = "\u25b6\u25b6"
STOP_BUTTON_GLYPH = "\u25a0"
PLAY_BUTTON_GLYPH = "\u25b6"
PAUSE_BUTTON_GLYPH = "\u275a\u275a"

PLAY_BUTTON_STYLE = """
QPushButton { background-color: #4c7a55; color: #ffffff; border: none; border-radius: 6px; }
QPushButton:hover { background-color: #578a61; }
QPushButton:pressed { background-color: #3f6748; }
"""
PAUSE_BUTTON_STYLE = """
QPushButton { background-color: #9a8340; color: #ffffff; border: none; border-radius: 6px; }
QPushButton:hover { background-color: #ab9349; }
QPushButton:pressed { background-color: #837036; }
"""
STOP_BUTTON_STYLE = """
QPushButton { background-color: #8a4b47; color: #ffffff; border: none; border-radius: 6px; }
QPushButton:hover { background-color: #9a5852; }
QPushButton:pressed { background-color: #75403c; }
"""

# Explicit background/text pair so selected rows stay readable under light and dark themes.
SELECTION_STYLE = """
QTableView { selection-background-color: #5a67a3; selection-color: #ffffff; }
QTableView::item:selected { background: #5a67a3; color: #ffffff; }
QTableView::item:selected:!active { background: #5a67a3; color: #ffffff; }
"""

PROGRESS_HEIGHT = 48
PROGRESS_STYLE = """
QSlider::groove:horizontal { height: 48px; background: #cfcfcf; border-radius: 4px; }
QSlider::sub-page:horizontal { background: #5a67a3; border-radius: 4px; }
QSlider::add-page:horizontal { background: #cfcfcf; border-radius: 4px; }
QSlider::handle:horizontal { width: 0px; margin: 0; background: transparent; border: none; }
"""
PROGRESS_TEXT_ON_FILL = "#ffffff"
PROGRESS_TEXT_ON_REST = "#333333"

# Second shade for alternating album runs, picked per theme lightness.
ALBUM_TINT_LIGHT = (232, 238, 247)
ALBUM_TINT_DARK = (38, 44, 56)

# Breathing room around every row except the seek bar, which reaches the window edges.
ROW_MARGIN = 9

# Transport buttons are square and sized from the screen height; actions get a share of its width.
TRANSPORT_BUTTON_SCALE = 0.05
TRANSPORT_BUTTON_RANGE = (36, 72)
ACTIONS_WIDTH_SHARE = 0.25

VOLUME_DEFAULT = 75
VOLUME_SLIDER_WIDTH = 120
MUTE_BUTTON_SIZE = 28
MUTE_ICON_SIZE = 18
MUTE_ICON_COLOR = "#b04a45"

# Duration only ever shows mm:ss, so it does not need content-based sizing.
DURATION_COLUMN_PADDING = 24
