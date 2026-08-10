# tag-gui
Tag GUI for audio files

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
    constants.py           columns, icon sizes, selection stylesheet
    utils.py               app data dir, mm:ss formatting
    icons.py               note pixmap/icon drawing
    models.py              Playlist dataclass
    tags.py                mutagen reads/writes, custom tag normalization
    widgets.py             SeekSlider, TagCheckItem, PlaylistTable
    main_window.py         MainWindow
    main.py                QApplication setup
```

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

## Features

- Drag and drop `.mp3` / `.flac` files into playlist tables, or use the Add Files button
- Select rows (shift/ctrl click, `Ctrl+A`) and press `Delete` to remove them; removing several asks for confirmation
- Playlist columns: Artist, Song, Album, Year, Duration
- Double-click row to play, plus Previous/Play/Pause/Stop/Next controls
- Clickable seek/progress bar
- Custom checkbox-tag columns via comma-separated textbox (persisted in `custom_tags.txt` under app data)
- Tag names are displayed as typed but stored as ASCII (`Yömusa` is written to files as `Yomusa`)
- Custom tag value `X` means checked; unchecking removes the tag from the file, checking writes it back
- Sortable/resizable columns with horizontal scrolling
- Tabbed M3U playlists persisted between sessions (`default.m3u`, `default1.m3u`, ...)
- Add Playlist button, or right-click the tab bar for Add / Remove playlist (removal asks first and deletes the `.m3u`)
- Double-click empty tab bar space to create the next default playlist
- Rename/Save As for playlist name and `.m3u` filename
