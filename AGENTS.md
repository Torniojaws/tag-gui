# Agent instructions

## Versioning

The app version lives in one place: `__version__` in `src/tag_gui/__init__.py`. It is shown
on the splash screen and in the window title. Follow semantic versioning (`MAJOR.MINOR.PATCH`)
and bump it as part of every change that alters app behavior:

- **New feature** (a new option, control, command or capability): bump the minor version and
  reset the patch, e.g. `1.0.3` -> `1.1.0`.
- **Small change** (bug fix, tweak, performance or wording change): bump the patch version,
  e.g. `1.1.0` -> `1.1.1`.
- **Major version**: only when the user asks for it.

Changes that do not affect the app, such as tests, documentation or build scripts alone, do
not need a bump. When one task contains several changes, bump once, by the largest step.

GitHub releases are named after this version: `vX.Y.Z` with the files
`tag-gui-vX.Y.Z-linux-x86_64` and `tag-gui-vX.Y.Z.exe`. Keep the `-linux-x86_64` suffix: a Linux
file name ending in `.Z` is taken for a file type extension (`.1` is a man page), so file managers
would not run it. If a release of the version already exists, CI publishes the next free
patch version instead and stamps it into the build; the source file is not changed by CI.

## Windows and Linux paths

The app is released for Windows and Linux, and CI runs the tests on both
(`.github/workflows/tests.yml`). A local run covers only one of them, so check every change
that handles file paths, in app code and in tests, against both before finishing:

- The same file is spelled differently depending on where the path comes from. Qt
  (`QUrl.toLocalFile()`, file dialogs, dropped or pasted URLs) uses forward slashes on every
  system, while `str(Path(...))` uses backslashes on Windows:
  `C:/Music/song.flac` vs `C:\Music\song.flac`.
- Never compare paths from different sources as plain strings. Compare `Path` objects, e.g.
  `Path(player.source().toLocalFile()) == Path(track)`. This also covers Windows treating
  file names as case-insensitive.
- Plain string comparison is fine only between the app's own track strings (playlist
  entries, the `Qt.UserRole` data of table rows, metadata cache keys), which are stored once
  and passed around unchanged. Turn a path from Qt or from the user into that form with
  `str(Path(...))` before storing it.
- Build and take apart paths with `pathlib`. Do not join with `/` or `\`, split on a
  separator, or hard-code one in an expected value of a test.

## Secrets

The Last.fm API key and shared secret live only in the gitignored
`src/tag_gui/_lastfm_keys.py` locally and in the `LASTFM_API_KEY` / `LASTFM_API_SECRET`
repository secrets in CI. Never commit them or copy them into any tracked file.
