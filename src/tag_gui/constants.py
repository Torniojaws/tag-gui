AUDIO_EXTENSIONS = {".mp3", ".flac", ".fla", ".wma", ".aac"}
AUDIO_FILE_FILTER = "Audio files (*.mp3 *.flac *.fla *.wma *.aac)"
APP_TITLE = "Tag GUI"
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
# Transport buttons are square and sized from the screen height; actions get a share of its width.
TRANSPORT_BUTTON_SCALE = 0.05
TRANSPORT_BUTTON_RANGE = (36, 72)
ACTIONS_WIDTH_SHARE = 0.25
DEFAULT_COLUMNS = ["Artist", "Duration", "Song", "Year", "Album"]
# Editable standard columns, paired with their mutagen easy-tag key. Duration is derived.
STANDARD_TAG_FIELDS = (("Artist", "artist"), ("Song", "title"), ("Year", "date"), ("Album", "album"))
ARTIST_COLUMN = DEFAULT_COLUMNS.index("Artist")
SONG_COLUMN = DEFAULT_COLUMNS.index("Song")
ALBUM_COLUMN = DEFAULT_COLUMNS.index("Album")
YEAR_COLUMN = DEFAULT_COLUMNS.index("Year")
DURATION_COLUMN = DEFAULT_COLUMNS.index("Duration")
# Duration only ever shows mm:ss, so it does not need content-based sizing.
DURATION_COLUMN_PADDING = 24
# Second shade for alternating album runs, picked per theme lightness.
ALBUM_TINT_LIGHT = (232, 238, 247)
ALBUM_TINT_DARK = (38, 44, 56)
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
