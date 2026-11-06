# Tag GUI

Tag GUI for audio file tagging, including custom tags that are configurable in the UI.

Features:

- Standard audio playback and playlist (m3u) features you'll find in any audio player
- Ability to edit standard tags, including mass editing
- Can add custom tags with checkboxes which will be written to the audio file metadata
- Can sort the files of course

This is almost entirely AI-generated, so no warranties :D

[![Tests and build](https://github.com/Torniojaws/tag-gui/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/Torniojaws/tag-gui/actions/workflows/build.yml)

<img width="3838" height="2086" alt="image" src="https://github.com/user-attachments/assets/8e4822cd-6ac2-490b-99f2-8711dbbf730d" />

## Downloads

1. Open https://github.com/Torniojaws/tag-gui/releases
2. Windows:
   1. Download the file `tag-gui-<datetime>.exe` and run it
3. For Debian-like (Linux Mint, Ubuntu, etc):
   1. Download the file `tag-gui-<datetime>-linux`
   2. Give it execute permissions with: `chmod +x tag-gui-<datetime>-linux`
   3. And then run it with `./tag-gui-<datetime>-linux`

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
        settings.py        user settings (skip step, timebar position) in settings.json
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
        transport.py       previous/play/stop/next
        volume.py          volume slider and mute
        progress.py        splash/dialog progress reporting
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

## Automated builds

Every push to `main` runs [.github/workflows/build.yml](.github/workflows/build.yml), which runs
the test suite on Windows and Linux, then builds the executable on both and publishes them as a
release tagged with the build time, e.g. `v202608101505` containing `tag-gui-202608101505.exe` and
`tag-gui-202608101505-linux`. A failing test stops the build, so no release is published.
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
- Clickable seek/progress bar, shown at the top, bottom or both (Settings...)
- While a song plays, `Left`/`Right` skip back/forward by a configurable step (1-60 s, default 5); skipping stops at the start of the song, and skipping past the end starts the next song, which a held key does not keep scrubbing
- Custom checkbox-tag columns via comma-separated textbox (persisted in `custom_tags.txt` under app data)
- Tag names are displayed as typed but stored as ASCII (`Yömusa` is written to files as `Yomusa`)
- Custom tag value `X` means checked; unchecking removes the tag from the file, checking writes it back
- Rows are shaded per album run: the shade flips whenever the album changes, so consecutive tracks of one album share a background
- Sortable/resizable columns with horizontal scrolling; a header click sorts descending first (checked tags on top) and scrolls back to the top
- Splash screen with a progress bar while playlists load at startup
- Tags read from files are cached in `metadata.json` under app data and reused until a file's timestamp changes, so restarts do not re-read every file
- Tabbed M3U playlists persisted between sessions (`default.m3u`, `default2.m3u`, ...)
- Double-click empty tab bar space to add the next `defaultN` playlist
- Double-click a tab to rename the playlist in place; the `.m3u` is renamed to an ASCII slug (`Äidille musaa` -> `aidille-musaa.m3u`) and the display name is stored in the file's `#PLAYLIST` header
- Close a playlist with its tab `X`, middle-click, or right-click -> Remove playlist; it asks first and never deletes the `.m3u`
- Load Playlist opens any existing `.m3u` as a new rightmost tab and keeps updating it in place; Save As points the playlist at a new file
- Copy files to dir copies every file in the current playlist into a chosen directory with a cancellable progress bar; originals are left untouched, files already there with the same name and size are skipped, and other name clashes get a numbered name (`song (2).flac`) instead of being overwritten
- Rename/Save As for playlist name and `.m3u` filename
