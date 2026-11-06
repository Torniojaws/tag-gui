"""Shared surface for the MainWindow mixins.

MainWindow is assembled from mixins that each own one slice of the window. Declaring the
state and the few cross-slice methods here lets every slice be read and checked on its own.
"""

from pathlib import Path
from typing import List

from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import QLineEdit, QMainWindow

from ..core.metadata import MetadataCache
from ..core.models import Playlist
from ..core.playlists import PlaylistStore
from ..core.settings import Settings
from .lastfm import LastfmController
from .sliders import SeekSlider
from .table import PlaylistTable
from .tabs import PlaylistTabs
from .transport import TransportBar
from .volume import VolumeControls


class WindowContext(QMainWindow):
    data_dir: Path
    custom_tags_file: Path
    settings_file: Path
    settings: Settings
    custom_tags: List[str]
    store: PlaylistStore
    metadata: MetadataCache
    splash: object
    current_track_index: int
    _updating_table: bool

    lastfm: LastfmController
    player: QMediaPlayer
    audio_output: QAudioOutput
    tabs: PlaylistTabs
    tags_input: QLineEdit
    search_input: QLineEdit
    transport: TransportBar
    volume: VolumeControls
    progress_top: SeekSlider
    progress_bottom: SeekSlider

    @property
    def playlists(self) -> List[Playlist]:
        raise NotImplementedError

    def current_playlist(self) -> Playlist:
        raise NotImplementedError

    def current_table(self) -> PlaylistTable:
        raise NotImplementedError

    def create_table(self) -> PlaylistTable:
        raise NotImplementedError

    def populate_table(self, table: PlaylistTable, playlist: Playlist) -> None:
        raise NotImplementedError

    def refresh_tracks(self, table: PlaylistTable, tracks: List[str]) -> None:
        raise NotImplementedError

    def save_state(self) -> None:
        raise NotImplementedError

    def load_playlist_dialog(self) -> None:
        raise NotImplementedError

    def save_playlist_as(self) -> None:
        raise NotImplementedError

    def open_settings(self) -> None:
        raise NotImplementedError

    def play_next(self) -> None:
        raise NotImplementedError

    def apply_search_to_current(self) -> None:
        raise NotImplementedError

    def update_search_count(self) -> None:
        raise NotImplementedError
