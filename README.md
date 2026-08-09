# tag-gui
Tag GUI for audio files

## Run

```bash
pip install -r requirements.txt
python app.py
```

## Build a standalone executable

```bash
pip install pyinstaller
python make_icon.py   # only needed if tag-gui.ico is missing or the icon changed
pyinstaller --noconfirm --clean --onefile --windowed --icon tag-gui.ico --name tag-gui app.py
```

The binary is written to `dist/tag-gui` (`dist\tag-gui.exe` on Windows) and needs no Python
installation. PyInstaller is not a cross-compiler, so build on the platform you target.

## Features

- Drag and drop `.mp3` / `.flac` files into playlist tables
- Playlist columns: Artist, Song, Album, Year, Duration
- Double-click row to play, plus Previous/Play/Pause/Stop/Next controls
- Clickable seek/progress bar
- Custom checkbox-tag columns via comma-separated textbox (persisted in `custom_tags.txt` under app data)
- Tag names are displayed as typed but stored as ASCII (`Yömusa` is written to files as `Yomusa`)
- Custom tag value `X` means checked; unchecking removes the tag from the file, checking writes it back
- Sortable/resizable columns with horizontal scrolling
- Tabbed M3U playlists persisted between sessions (`default.m3u`, `default1.m3u`, ...)
- Double-click tab bar to create the next default playlist
- Rename/Save As for playlist name and `.m3u` filename
