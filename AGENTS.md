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

GitHub releases are named after this version: `vX.Y.Z` with the files `tag-gui-vX.Y.Z` (Linux)
and `tag-gui-vX.Y.Z.exe`. If a release of the version already exists, CI publishes the next free
patch version instead and stamps it into the build; the source file is not changed by CI.

## Secrets

The Last.fm API key and shared secret live only in the gitignored
`src/tag_gui/_lastfm_keys.py` locally and in the `LASTFM_API_KEY` / `LASTFM_API_SECRET`
repository secrets in CI. Never commit them or copy them into any tracked file.
