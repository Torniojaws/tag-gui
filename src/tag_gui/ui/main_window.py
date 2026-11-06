"""Assembles the window from the playlist, file, tag and playback slices."""

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..constants import WINDOW_TITLE
from ..core.metadata import MetadataCache
from ..core.models import Playlist
from ..core.playlists import PlaylistStore
from ..core.settings import load_settings, save_settings
from ..core.utils import app_data_dir
from .dialogs import SettingsDialog
from .file_actions import FileActionsMixin
from .lastfm import LastfmController
from .playback import PlaybackMixin
from .playlist_actions import PlaylistActionsMixin
from .progress import progress_reporter
from .search import SearchMixin
from .sorting import SortMixin
from .styles import ROW_MARGIN
from .table import PlaylistTable
from .table_fill import fill_table, refresh_rows
from .tag_actions import TagActionsMixin


class MainWindow(
    PlaylistActionsMixin,
    FileActionsMixin,
    TagActionsMixin,
    PlaybackMixin,
    SearchMixin,
    SortMixin,
):
    def __init__(self, splash=None):
        QMainWindow.__init__(self)
        self.setWindowTitle(WINDOW_TITLE)
        self.data_dir = app_data_dir()
        self.custom_tags_file = self.data_dir / "custom_tags.txt"
        self.settings_file = self.data_dir / "settings.json"
        self.settings = load_settings(self.settings_file)

        self.splash = splash
        self.custom_tags: List[str] = []
        self.store = PlaylistStore(self.data_dir)
        self.current_track_index = -1
        self._updating_table = False
        self.metadata = MetadataCache(self.data_dir / "metadata.json")
        self.metadata.load()

        self.lastfm = LastfmController(self.data_dir, self)
        self.lastfm.session_lost.connect(self.on_lastfm_session_lost)
        self._build_player()
        self._build_playback_widgets()
        self._build_tabs()
        self._build_layout()
        self.apply_settings()
        self.load_state()

    def _build_layout(self):
        tabs_row = QHBoxLayout()
        tabs_row.setContentsMargins(ROW_MARGIN, 0, ROW_MARGIN, 0)
        tabs_row.addWidget(self.tabs)

        left = QHBoxLayout()
        left.addWidget(self.volume, 0, Qt.AlignVCenter)
        left.addWidget(self._build_sort_controls(), 0, Qt.AlignVCenter)
        left.addStretch(1)

        right = QHBoxLayout()
        right.addStretch(1)
        right.addWidget(self._build_actions())

        # Equal stretch on both sides keeps the transport centered in the window, not just
        # in the space left over by the action buttons.
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(ROW_MARGIN, 0, ROW_MARGIN, 6)
        controls_row.addLayout(left, 1)
        controls_row.addWidget(self.transport)
        controls_row.addLayout(right, 1)

        central = QWidget()
        layout = QVBoxLayout(central)
        # Only the seek bar reaches the window edges, so the margins live on the other rows.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.progress_top)
        layout.addLayout(self._build_tags_row())
        layout.addWidget(self._build_search_row())
        layout.addLayout(tabs_row)
        layout.addLayout(controls_row)
        layout.addWidget(self.progress_bottom)
        self.setCentralWidget(central)

    # --------------------------------------------------------------- settings

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self, lastfm=self.lastfm)
        if dialog.exec() != QDialog.Accepted:
            return
        self.settings = dialog.settings()
        save_settings(self.settings_file, self.settings)
        self.apply_settings()

    def apply_settings(self):
        self.progress_top.setVisible(self.settings.timebar_top)
        self.progress_bottom.setVisible(self.settings.timebar_bottom)
        self.transport.set_shuffle(self.settings.shuffle)

    # ------------------------------------------------------------- accessors

    @property
    def playlists(self) -> List[Playlist]:
        return self.store.playlists

    def current_playlist(self) -> Playlist:
        return self.playlists[self.tabs.currentIndex()]

    def current_table(self) -> PlaylistTable:
        return self.tabs.currentWidget()

    def create_table(self) -> PlaylistTable:
        table = PlaylistTable(
            self.add_tracks_to_current_playlist,
            self.remove_selected_tracks,
            self.copy_selected_tracks,
            self.paste_tracks,
        )
        table.customContextMenuRequested.connect(self.on_table_context_menu)
        table.itemDoubleClicked.connect(self.on_item_double_clicked)
        table.itemChanged.connect(self.on_item_changed)
        table.filter_applied.connect(self.update_search_count)
        return table

    # ------------------------------------------------------------------ table

    def populate_table(self, table: PlaylistTable, playlist: Playlist):
        update, finish = progress_reporter(
            self, self.splash, f"Reading tags for {playlist.name}", len(playlist.tracks)
        )
        self._updating_table = True
        try:
            fill_table(table, playlist, self.custom_tags, self.metadata, update)
        finally:
            finish()
            self._updating_table = False

    def refresh_tracks(self, table: PlaylistTable, tracks: List[str]):
        self._updating_table = True
        try:
            refresh_rows(table, tracks, self.custom_tags, self.metadata)
        finally:
            self._updating_table = False

    # ------------------------------------------------------------------ state

    def load_state(self):
        self.load_custom_tags()
        active_index = self.store.load()
        for playlist in self.playlists:
            table = self.create_table()
            self.tabs.addTab(table, playlist.name)
            self.populate_table(table, playlist)
        self.tabs.setCurrentIndex(min(active_index, self.tabs.count() - 1))
        self.splash = None
        self.save_state()

    def save_state(self):
        self.store.save(self.tabs.currentIndex())
        self.metadata.save(keep=self.store.all_tracks())

    def on_lastfm_session_lost(self):
        QMessageBox.warning(
            self,
            "Last.fm",
            "Last.fm no longer accepts this app's login, so scrobbling has stopped.\n"
            "Connect again in Settings; plays since then are kept and sent afterwards.",
        )

    def closeEvent(self, event):
        self.cancel_sorting()
        self.lastfm.shutdown()
        self.save_custom_tags()
        self.save_state()
        self.metadata.save()
        super().closeEvent(event)
