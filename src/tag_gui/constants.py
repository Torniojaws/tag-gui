AUDIO_EXTENSIONS = {".mp3", ".flac", ".fla", ".wma", ".aac"}
AUDIO_FILE_FILTER = "Audio files (*.mp3 *.flac *.fla *.wma *.aac)"
DEFAULT_COLUMNS = ["Artist", "Song", "Album", "Year", "Duration"]
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
APP_ID = "tag-gui.tag-gui"
# Rows are filled in chunks of this size so the progress dialog stays responsive.
POPULATE_BATCH = 25
# Reading tags is slow, so only show progress once a playlist is this big.
PROGRESS_THRESHOLD = 100
# Explicit background/text pair so selected rows stay readable under light and dark themes.
SELECTION_STYLE = """
QTableView { selection-background-color: #5a67a3; selection-color: #ffffff; }
QTableView::item:selected { background: #5a67a3; color: #ffffff; }
QTableView::item:selected:!active { background: #5a67a3; color: #ffffff; }
"""
