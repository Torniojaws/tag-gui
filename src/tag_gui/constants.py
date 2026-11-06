"""Data rules: file types, columns and batching. Visual constants live in ui/styles.py."""

APP_ID = "tag-gui.tag-gui"
APP_TITLE = "Tag GUI"

AUDIO_EXTENSIONS = {".mp3", ".flac", ".fla", ".wma", ".aac"}
AUDIO_FILE_FILTER = "Audio files (*.mp3 *.flac *.fla *.wma *.aac)"
AUDIO_FILE_FILTER_WITH_WAV = "Audio files (*.mp3 *.flac *.fla *.wma *.aac *.wav)"
PLAYLIST_FILE_FILTER = "Playlists (*.m3u *.m3u8)"

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

DEFAULT_COLUMNS = ["Artist", "Duration", "Song", "Year", "Album"]
# Editable standard columns, paired with their mutagen easy-tag key. Duration is derived.
STANDARD_TAG_FIELDS = (("Artist", "artist"), ("Song", "title"), ("Year", "date"), ("Album", "album"))
ARTIST_COLUMN = DEFAULT_COLUMNS.index("Artist")
SONG_COLUMN = DEFAULT_COLUMNS.index("Song")
ALBUM_COLUMN = DEFAULT_COLUMNS.index("Album")
YEAR_COLUMN = DEFAULT_COLUMNS.index("Year")
DURATION_COLUMN = DEFAULT_COLUMNS.index("Duration")
# The column whose items carry the file path in Qt.UserRole.
PATH_COLUMN = 0
LEFT_ALIGNED_HEADERS = tuple(
    DEFAULT_COLUMNS.index(name) for name in ("Artist", "Duration", "Song", "Album")
)
# The Ctrl+F filter keeps rows where any of these columns contains the search term.
SEARCH_COLUMNS = (ARTIST_COLUMN, SONG_COLUMN, ALBUM_COLUMN)

# Rows are filled in chunks of this size so the progress dialog stays responsive.
POPULATE_BATCH = 25
# Reading tags is slow, so only show progress once a playlist is this big.
PROGRESS_THRESHOLD = 100
