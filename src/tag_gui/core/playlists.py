import json
from pathlib import Path
from typing import List, Set, Tuple

from .models import Playlist
from .utils import slugify

M3U_SUFFIXES = (".m3u", ".m3u8")
NAME_HEADER = "#PLAYLIST:"


class PlaylistStore:
    """Owns the playlist list and everything that reads or writes it on disk."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.state_file = data_dir / "playlists.json"
        self.playlists: List[Playlist] = []

    def path_for(self, playlist: Playlist) -> Path:
        """Loaded playlists keep their own location; the app's own ones live in the data dir."""
        path = Path(playlist.file_name)
        return path if path.is_absolute() else self.data_dir / path

    def all_tracks(self) -> Set[str]:
        return {track for playlist in self.playlists for track in playlist.tracks}

    @staticmethod
    def read_m3u(path: Path) -> Tuple[str, List[str]]:
        name = ""
        tracks: List[str] = []
        if not path.exists():
            return name, tracks
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(NAME_HEADER):
                name = line[len(NAME_HEADER):].strip()
            elif line and not line.startswith("#"):
                tracks.append(line)
        return name, tracks

    def write_m3u(self, playlist: Playlist) -> None:
        # The file name is ASCII, so the display name is kept in the standard #PLAYLIST header.
        lines = ["#EXTM3U", f"{NAME_HEADER}{playlist.name}"] + playlist.tracks
        self.path_for(playlist).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load(self) -> int:
        """Read the saved playlists and return the index that was active."""
        active_index = 0
        self.playlists = []
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.playlists = [
                Playlist(name=entry["name"], file_name=entry["file_name"])
                for entry in state.get("playlists", [])
            ]
            active_index = int(state.get("active_index", 0))
        for playlist in self.playlists:
            playlist.tracks = self.read_m3u(self.path_for(playlist))[1]
        if not self.playlists:
            self.playlists = [Playlist(name="default", file_name="default.m3u")]
        return active_index

    def save(self, active_index: int) -> None:
        for playlist in self.playlists:
            self.write_m3u(playlist)
        state = {
            "active_index": active_index,
            "playlists": [{"name": p.name, "file_name": p.file_name} for p in self.playlists],
        }
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def unique_file_name(self, candidate: str, skip_index: int = -1) -> str:
        used = {p.file_name.lower() for i, p in enumerate(self.playlists) if i != skip_index}
        if candidate.lower() not in used:
            return candidate
        stem = candidate[: -len(".m3u")]
        suffix = 2
        while f"{stem}-{suffix}.m3u".lower() in used:
            suffix += 1
        return f"{stem}-{suffix}.m3u"

    def next_default(self) -> Playlist:
        used = {p.name.casefold() for p in self.playlists}
        if "default" not in used:
            return Playlist(name="default", file_name=self.unique_file_name("default.m3u"))
        index = 2
        while f"default{index}" in used:
            index += 1
        name = f"default{index}"
        return Playlist(name=name, file_name=self.unique_file_name(f"{name}.m3u"))

    def rename(self, index: int, new_name: str) -> bool:
        """Rename the playlist and its file, returning False when nothing changed."""
        playlist = self.playlists[index]
        new_name = new_name.strip()
        if not new_name or new_name == playlist.name:
            return False
        old_path = self.path_for(playlist)
        playlist.name = new_name
        slug = f"{slugify(new_name)}.m3u"
        if old_path.parent == self.data_dir:
            playlist.file_name = self.unique_file_name(slug, index)
        else:
            # A loaded playlist is renamed where it lives, not moved into the data dir.
            playlist.file_name = str(old_path.with_name(slug))
        self.write_m3u(playlist)
        if self.path_for(playlist) != old_path and old_path.exists():
            old_path.unlink()
        return True

    def move(self, from_index: int, to_index: int) -> None:
        self.playlists.insert(to_index, self.playlists.pop(from_index))
