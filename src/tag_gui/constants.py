AUDIO_EXTENSIONS = {".mp3", ".flac"}
DEFAULT_COLUMNS = ["Artist", "Song", "Album", "Year", "Duration"]
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_ID = "tag-gui.tag-gui"
# Explicit background/text pair so selected rows stay readable under light and dark themes.
SELECTION_STYLE = """
QTableView { selection-background-color: #5a67a3; selection-color: #ffffff; }
QTableView::item:selected { background: #5a67a3; color: #ffffff; }
QTableView::item:selected:!active { background: #5a67a3; color: #ffffff; }
"""
