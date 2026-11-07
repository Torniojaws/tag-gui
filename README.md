# Tag GUI

Tag GUI for audio file tagging, including custom tags that are configurable in the UI.

Features:

- Standard audio playback and playlist (m3u) features you'll find in any audio player
- Ability to edit standard tags, including mass editing
- Can add custom tags with checkboxes which will be written to the audio file metadata
- Can sort the files of course

This is almost entirely AI-generated, so no warranties :D

[![Tests](https://github.com/Torniojaws/tag-gui/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/Torniojaws/tag-gui/actions/workflows/tests.yml)
[![Build and release](https://github.com/Torniojaws/tag-gui/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/Torniojaws/tag-gui/actions/workflows/build.yml)

<img width="3838" height="2108" alt="image" src="https://github.com/user-attachments/assets/5c2aab1a-f2c7-493f-85ec-eeb473df9106" />

## Downloads

1. Open https://github.com/Torniojaws/tag-gui/releases
2. Windows:
   1. Download the file `tag-gui-v<version>.exe` (e.g. `tag-gui-v1.0.0.exe`) and run it
3. For Debian-like (Linux Mint, Ubuntu, etc):
   1. Download the file `tag-gui-v<version>-linux-x86_64` (e.g. `tag-gui-v1.0.0-linux-x86_64`)
   2. Give it execute permissions with: `chmod +x tag-gui-v1.0.0-linux-x86_64`
   3. And then run it with `./tag-gui-v1.0.0-linux-x86_64`
4. Optional: to scrobble to Last.fm, open Settings -> Connect to Last.fm... and allow Tag GUI in
   the browser. No API key or other setup is needed with the released builds.

## Run

```bash
pip install -r requirements.txt
python app.py
```

## Layout

```
app.py                     entry point (adds src/ to sys.path, calls tag_gui.main)
make_icon.py               writes tag-gui.ico
build.py / build.cmd       build tasks
src/tag_gui/
    constants.py           file types, columns, batching
    main.py                QApplication setup
    core/                  no Qt widgets, only files, tags and playlists
        models.py          Playlist dataclass
        playlists.py       PlaylistStore: m3u read/write, state file, naming
        tags.py            mutagen reads/writes, custom tag normalization
        metadata.py        cached track fields and tag states
        scanning.py        recursive audio file collection
        settings.py        user settings (skip step, timebar position, shuffle, scrobbling pause) in settings.json
        copying.py         copying playlist files to another directory
        sorting.py         playlist orders: by path, random, by release year
        shuffle.py         shuffle picks avoiding recent artists, albums and songs
        lastfm.py          Last.fm API client: signing, browser login, scrobbles
        listening.py       when a play counts as a scrobble
        scrobbling.py      scrobble queue that survives being offline
        utils.py           app data dir, slugify, mm:ss formatting
    ui/
        styles.py          colours, glyphs, sizes
        sizing.py          screen-derived widget sizes
        icons.py           note and speaker drawing
        splash.py          startup window
        dialogs.py         standard tag editor and settings window
        table.py           PlaylistTable, check delegate, album shading
        table_fill.py      filling and refreshing rows
        tabs.py            renameable tab bar
        sliders.py         seek bar with in-bar time text
        transport.py       previous/play/stop/next and the shuffle checkbox
        volume.py          volume slider and mute
        progress.py        splash/dialog progress reporting
        spinner.py         small busy indicator
        search.py          Ctrl+F filter bar
        sorting.py         sort dropdown and background year sort
        lastfm.py          Last.fm login state, play tracking and network thread
        window_base.py     state shared by the window slices
        playlist_actions.py  tab bar and playlist commands
        file_actions.py    add/load/save row, adding and removing tracks
        tag_actions.py     custom tag row and tag writing
        playback.py        player, transport widgets, playback commands
        main_window.py     assembles the slices into the window
tests/                     pytest suite, run with `python build.py test`
```

## Tests

```bash
pip install pytest
python build.py test
```

The suite covers `core/` (m3u and state files, tag normalization and writing, the metadata cache,
file scanning) plus one offscreen run of the real `MainWindow`. Test audio is synthesised by
[tests/conftest.py](tests/conftest.py), so no binary fixtures are checked in, and the window tests
set `QT_QPA_PLATFORM=offscreen` so they need no display.

## Build a standalone executable

[`python build.py`](build.py) runs the build steps in sequence and needs nothing but Python:

`.\build` is the [`build.cmd`](build.cmd) wrapper; PowerShell requires the `.\` prefix, `cmd.exe`
does not. On macOS/Linux run `python build.py <task>` instead.

The equivalent commands by hand are:

```bash
pip install pyinstaller
python make_icon.py   # only needed if tag-gui.ico is missing or the icon changed
pyinstaller --noconfirm --clean --onefile --windowed --icon tag-gui.ico --name tag-gui app.py
```

The binary is written to `dist/tag-gui` (`dist\tag-gui.exe` on Windows) and needs no Python
installation. PyInstaller is not a cross-compiler, so build on the platform you target.

### Last.fm API key (only when running or building from source)

If you use a downloaded release, skip this section: the released builds already contain the
app's Last.fm API key, so you only need to click Settings -> Connect to Last.fm... and allow Tag
GUI on last.fm with your own account.

Running `python app.py` or building your own executable needs the API key and shared secret in
`src/tag_gui/_lastfm_keys.py`:

```python
API_KEY = "..."
API_SECRET = "..."
```

Use your own key from https://www.last.fm/api/account/create. The file is gitignored and must
never be committed. Without it the app works normally, and the Settings window shows scrobbling
as unavailable.

The GitHub release builds write this file from the repository secrets `LASTFM_API_KEY` and
`LASTFM_API_SECRET` (Settings -> Secrets and variables -> Actions -> Repository secrets).

## Automated builds

Every push, on any branch, runs the test suite on Windows and Linux with
[.github/workflows/tests.yml](.github/workflows/tests.yml), unless it only changes Markdown files
(such as this README) or `LICENSE`. That workflow never builds or releases anything.

Pushes to `main` that change the app also run
[.github/workflows/build.yml](.github/workflows/build.yml); pushes that only change Markdown files,
`LICENSE` or files under `tests/` skip it. It runs the same test workflow first, then builds the
executable on Windows and Linux and publishes them as a release tagged with the app version, e.g.
`v1.0.0` containing `tag-gui-v1.0.0.exe` and `tag-gui-v1.0.0-linux-x86_64`. The Linux file names
the OS and CPU it runs on, the usual convention for downloadable binaries, which also keeps the
name from ending in a number like `.0`: file managers would take that for a file type extension
(e.g. `.1` is a man page) instead of recognizing the executable. The version comes from
`__version__` in `src/tag_gui/__init__.py` (see
[AGENTS.md](AGENTS.md) for when to bump it). If a release of that version already exists, the
patch number is increased until it is free (`v1.0.1`, `v1.0.2`, ...) and the build is stamped
with that version, so the app always shows the version it was released as. A failing test stops
the build, so no release is published.
Releases are linked from the repository front page; the same files are also attached to the
workflow run as artifacts.

## Features

- Drag and drop audio files (`.mp3`, `.flac`, `.fla`, `.wma`, `.aac`) or whole folders into playlist tables, or use the Add Files button
- Copy and paste one or more selected songs between playlists
- Dropped folders are scanned recursively with a cancellable progress dialog; tags are then read in batches so large trees stay responsive
- Select rows (shift/ctrl click, `Ctrl+A`) and press `Delete` to remove them; removing several asks for confirmation
- `Home`/`End` scroll the playlist to the top/bottom without changing the selection
- `Ctrl+F` opens a filter bar above the playlists and `Ctrl+F` (or `Esc`) closes it again; the list narrows as you type to rows whose Artist, Song or Album contains the text (case-insensitive), shows the match count, and clearing or closing the filter brings back the full list. Next/Previous play only the visible rows, and selection-based actions (Delete, copy, Edit tags) ignore hidden rows
- The Sort playlist dropdown next to the mute button reorders only the current playlist: by full file path, randomly (a new order every time), or by release year oldest/newest first. Year sorting keeps each album together in track (and disc) order, falling back to song title and then path when an album has no track numbers; albums of the same year stay in their playlist order and files without a year go last. Year sorting runs in the background with a spinner, so the window stays usable; track numbers are read along with the other tags and cached, so only files cached by older versions need a one-time read. A green "Sorting completed" note fades out after 5 seconds
- Playlist columns: Artist, Duration, Song, Year, Album
- Standard tags are edited via right-click -> Edit tags, which writes only the fields you changed, across every selected row (Duration is read-only)
- Double-click row to play, plus Previous/Play/Pause/Stop/Next controls
- Shuffle checkbox next to the Next button (remembered between sessions): Next and the end of a song pick a random visible track that shares no artist, album or song with the last 10 played, preferring tracks not yet heard this round. Songs are matched fuzzily, so `Song (Cover)`, `Song - Live 2018` and `Song Live at Wembley` count as `Song`. If everything clashes (e.g. a single-artist playlist) it relaxes the rule instead of stopping. Previous steps back through the tracks that actually played
- Last.fm scrobbling: Settings -> Connect to Last.fm opens last.fm in the browser, where you allow Tag GUI; the app never sees your password and keeps only the session key (`lastfm.json` under app data). Each track sends "now playing" and is scrobbled once it has played for half its length or 4 minutes (tracks of 30 s or less never count). Only time actually played counts, so pausing or skipping ahead does not, and files without artist and title tags are not scrobbled. Network calls run in the background; plays that cannot be sent (offline, Last.fm down, logged out) are kept in `scrobble_queue.json` and sent later. The "Pause scrobbling" checkbox in Settings (remembered between sessions) stops scrobbling and "now playing" updates; tracks heard while it is checked are not tracked, so only tracks started after unchecking it are scrobbled
- Clickable seek/progress bar, shown at the top, bottom or both (Settings...)
- While a song plays, `Left`/`Right` skip back/forward by a configurable step (1-60 s, default 5); skipping stops at the start of the song, and skipping past the end starts the next song, which a held key does not keep scrubbing
- Custom checkbox-tag columns via comma-separated textbox (persisted in `custom_tags.txt` under app data)
- Tag names are displayed as typed but stored as ASCII (`Yömusa` is written to files as `Yomusa`)
- Custom tag value `X` means checked; unchecking removes the tag from the file, checking writes it back
- Rows are shaded per album run: the shade flips whenever the album changes, so consecutive tracks of one album share a background
- Sortable/resizable columns with horizontal scrolling; a header click sorts descending first (checked tags on top) and scrolls back to the top
- Splash screen with the app version and a progress bar while playlists load at startup; the version is also shown in the window title
- Tags read from files are cached in `metadata.json` under app data and reused until a file's timestamp changes, so restarts do not re-read every file
- Tabbed M3U playlists persisted between sessions (`default.m3u`, `default2.m3u`, ...)
- Double-click empty tab bar space to add the next `defaultN` playlist
- Double-click a tab to rename the playlist in place; the `.m3u` is renamed to an ASCII slug (`Äidille musaa` -> `aidille-musaa.m3u`) and the display name is stored in the file's `#PLAYLIST` header
- Close a playlist with its tab `X`, middle-click, or right-click -> Remove playlist; it asks first and never deletes the `.m3u`
- Load Playlist opens any existing `.m3u` as a new rightmost tab and keeps updating it in place; Save As points the playlist at a new file
- Copy files to dir copies every file in the current playlist into a chosen directory with a cancellable progress bar; originals are left untouched, files already there with the same name and size are skipped, and other name clashes get a numbered name (`song (2).flac`) instead of being overwritten
- Rename/Save As for playlist name and `.m3u` filename
