"""Tab bar wiring and the playlist create/load/rename/remove commands."""

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMenu, QMessageBox

from ..constants import PLAYLIST_FILE_FILTER
from ..core.models import Playlist
from ..core.utils import slugify
from .tabs import PlaylistTabs
from .window_base import WindowContext


class PlaylistActionsMixin(WindowContext):
    def _build_tabs(self):
        self.tabs = PlaylistTabs()
        self.tabs.empty_double_clicked.connect(self.add_playlist)
        self.tabs.tabBarDoubleClicked.connect(self.on_tabbar_double_clicked)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabCloseRequested.connect(self.remove_playlist)
        tab_bar = self.tabs.tabBar()
        tab_bar.customContextMenuRequested.connect(self.on_tabbar_context_menu)
        tab_bar.tabMoved.connect(self.on_tab_moved)
        tab_bar.name_edited.connect(self.rename_playlist_to)
        tab_bar.middle_clicked.connect(self.remove_playlist)

    def on_tabbar_double_clicked(self, index):
        if index != -1:
            self.tabs.tabBar().edit_tab(index)

    def on_tabbar_context_menu(self, pos):
        tab_bar = self.tabs.tabBar()
        index = tab_bar.tabAt(pos)
        menu = QMenu(self)
        add_action = menu.addAction("Add playlist")
        load_action = menu.addAction("Load playlist...")
        remove_action = menu.addAction("Remove playlist") if index != -1 else None
        chosen = menu.exec(tab_bar.mapToGlobal(pos))
        if chosen is add_action:
            self.add_playlist()
        elif chosen is load_action:
            self.load_playlist_dialog()
        elif chosen is not None and chosen is remove_action:
            self.remove_playlist(index)

    def add_playlist(self):
        self.open_playlist(self.store.next_default())

    def open_playlist(self, playlist: Playlist):
        self.playlists.append(playlist)
        table = self.create_table()
        self.tabs.addTab(table, playlist.name)
        self.populate_table(table, playlist)
        self.tabs.setCurrentWidget(table)
        self.save_state()

    def load_playlist_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Playlist", str(self.data_dir), PLAYLIST_FILE_FILTER
        )
        if not path:
            return
        chosen = Path(path)
        for index, playlist in enumerate(self.playlists):
            if self.store.path_for(playlist) == chosen:
                self.tabs.setCurrentIndex(index)
                return
        name, tracks = self.store.read_m3u(chosen)
        self.open_playlist(Playlist(name=name or chosen.stem, file_name=str(chosen), tracks=tracks))

    def remove_playlist(self, index: int):
        if not 0 <= index < len(self.playlists):
            return
        playlist = self.playlists[index]
        answer = QMessageBox.question(
            self,
            "Remove playlist",
            f"Remove playlist '{playlist.name}' from the list?\n"
            f"{self.store.path_for(playlist)} is kept on disk and can be loaded again.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        widget = self.tabs.widget(index)
        self.tabs.removeTab(index)
        widget.deleteLater()
        del self.playlists[index]
        self.current_track_index = -1
        if self.playlists:
            self.save_state()
        else:
            self.add_playlist()

    def rename_playlist_to(self, index: int, new_name: str):
        if not 0 <= index < len(self.playlists):
            return
        if self.store.rename(index, new_name):
            self.tabs.setTabText(index, self.playlists[index].name)
            self.save_state()

    def save_playlist_as(self):
        index = self.tabs.currentIndex()
        if index < 0:
            return
        playlist = self.playlists[index]
        suggested = self.store.path_for(playlist).with_name(f"{slugify(playlist.name)}.m3u")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Playlist As", str(suggested), PLAYLIST_FILE_FILTER
        )
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() not in (".m3u", ".m3u8"):
            target = target.with_suffix(".m3u")
        # The previous file is left alone; the playlist simply continues in its new location.
        playlist.file_name = str(target)
        self.save_state()

    def on_tab_changed(self, _index):
        self.current_track_index = -1
        self.apply_search_to_current()

    def on_tab_moved(self, from_index: int, to_index: int):
        self.store.move(from_index, to_index)
        self.save_state()
