"""The Add/Load/Save action row plus adding and removing tracks."""

from pathlib import Path
from typing import List

from PySide6.QtCore import QUrl, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QWidget,
)

from ..constants import AUDIO_FILE_FILTER, AUDIO_FILE_FILTER_WITH_WAV, POPULATE_BATCH
from ..core.scanning import collect_audio_files
from .sizing import screen_geometry
from .styles import ACTIONS_WIDTH_SHARE
from .table_fill import row_for_path, selected_tracks
from .window_base import WindowContext


class FileActionsMixin(WindowContext):
    def _build_actions(self) -> QWidget:
        add_btn = QPushButton("Add Files")
        load_btn = QPushButton("Load Playlist")
        save_as_btn = QPushButton("Save As...")
        add_btn.clicked.connect(self.add_files_dialog)
        load_btn.clicked.connect(self.load_playlist_dialog)
        save_as_btn.clicked.connect(self.save_playlist_as)

        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        for button in (add_btn, load_btn, save_as_btn):
            layout.addWidget(button)
        geometry = screen_geometry()
        if geometry:
            actions.setMaximumWidth(round(geometry.width() * ACTIONS_WIDTH_SHARE))
        return actions

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add Files", "", AUDIO_FILE_FILTER_WITH_WAV)
        if not paths:
            return
        wav_paths = [p for p in paths if Path(p).suffix.lower() == ".wav"]
        if wav_paths:
            QMessageBox.warning(
                self,
                "Unsupported format",
                "WAV files do not support tags and metadata and cannot be added.",
            )
        audio_paths = [p for p in paths if Path(p).suffix.lower() != ".wav"]
        if audio_paths:
            self.add_tracks_to_current_playlist([str(Path(p)) for p in audio_paths])

    def add_tracks_to_current_playlist(self, paths: List[str]):
        tracks = self.scan_for_audio_files(paths)
        if not tracks:
            return
        playlist = self.current_playlist()
        known = set(playlist.tracks)
        for track in tracks:
            if track not in known:
                known.add(track)
                playlist.tracks.append(track)
        self.populate_table(self.current_table(), playlist)
        self.save_state()

    def scan_for_audio_files(self, paths: List[str]) -> List[str]:
        """Expand dropped folders into audio files, reporting progress for big trees."""
        progress = QProgressDialog("Scanning for audio files...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Add files")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(300)

        def on_progress(count: int):
            if count % POPULATE_BATCH:
                return
            progress.setLabelText(f"Scanning for audio files... {count} found")
            QApplication.processEvents()

        try:
            return collect_audio_files(paths, on_progress, progress.wasCanceled)
        finally:
            progress.close()

    def remove_selected_tracks(self):
        table = self.current_table()
        paths = selected_tracks(table)
        if not paths:
            return
        if len(paths) > 1:
            answer = QMessageBox.question(
                self,
                "Remove files",
                f"Remove {len(paths)} files from the playlist?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        removed = {Path(p) for p in paths}
        playing = self.player.source().toLocalFile()
        playlist = self.current_playlist()
        playlist.tracks = [t for t in playlist.tracks if Path(t) not in removed]
        for track in paths:
            self.metadata.discard(track)
        self.populate_table(table, playlist)

        if playing and Path(playing) in removed:
            self.player.stop()
            self.player.setSource(QUrl())
            self.current_track_index = -1
        else:
            self.current_track_index = row_for_path(table, playing)
        self.save_state()
