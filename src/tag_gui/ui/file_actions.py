"""The Add/Load/Save action row plus adding and removing tracks."""

from pathlib import Path
from typing import List

from PySide6.QtCore import QMimeData, QUrl, Qt
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
from ..core.copying import copy_files, total_bytes
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
        copy_to_dir_btn = QPushButton("Copy files to dir")
        settings_btn = QPushButton("Settings...")
        add_btn.clicked.connect(self.add_files_dialog)
        load_btn.clicked.connect(self.load_playlist_dialog)
        save_as_btn.clicked.connect(self.save_playlist_as)
        copy_to_dir_btn.clicked.connect(self.copy_playlist_to_dir)
        settings_btn.clicked.connect(self.open_settings)

        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        for button in (add_btn, load_btn, save_as_btn, copy_to_dir_btn, settings_btn):
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

    def copy_playlist_to_dir(self):
        """Copy the current playlist's files into a chosen directory; originals stay put."""
        tracks = list(self.current_playlist().tracks)
        if not tracks:
            QMessageBox.information(self, "Copy files", "The playlist has no files to copy.")
            return
        target = QFileDialog.getExistingDirectory(self, "Copy files to directory")
        if not target:
            return

        # QProgressDialog takes an int range, so count KiB to stay clear of overflow.
        total_kib = max(1, total_bytes(tracks) // 1024)
        progress = QProgressDialog(
            f"Copying {len(tracks)} files to {target}...", "Cancel", 0, total_kib, self
        )
        progress.setWindowTitle("Copy files to dir")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)

        def on_progress(done_bytes: int):
            progress.setValue(min(total_kib, done_bytes // 1024))
            QApplication.processEvents()

        try:
            result = copy_files(tracks, target, on_progress, progress.wasCanceled)
        except OSError as error:
            QMessageBox.warning(self, "Copy files", f"Could not copy to {target}:\n{error}")
            return
        finally:
            progress.close()

        lines = [f"Copied {len(result.copied)} of {len(tracks)} files to {target}."]
        if result.cancelled:
            lines.append("Copying was cancelled.")
        if result.skipped:
            lines.append(f"{len(result.skipped)} already existed there and were skipped.")
        if result.missing:
            lines.append(f"{len(result.missing)} could not be found.")
        if result.failed:
            lines.append(f"{len(result.failed)} failed to copy.")
        notify = QMessageBox.warning if result.missing or result.failed else QMessageBox.information
        notify(self, "Copy files", "\n".join(lines))

    def copy_selected_tracks(self):
        paths = selected_tracks(self.current_table())
        if not paths:
            return
        # File URLs let the tracks be pasted into a file manager too, and vice versa.
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
        mime.setText("\n".join(paths))
        QApplication.clipboard().setMimeData(mime)

    def paste_tracks(self):
        mime = QApplication.clipboard().mimeData()
        if not mime or not mime.hasUrls():
            return
        paths = [str(Path(url.toLocalFile())) for url in mime.urls() if url.isLocalFile()]
        if paths:
            self.add_tracks_to_current_playlist(paths)

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
        self._updating_table = True
        try:
            table.remove_tracks(paths)
        finally:
            self._updating_table = False

        if playing and Path(playing) in removed:
            self.player.stop()
            self.player.setSource(QUrl())
            self.current_track_index = -1
        else:
            self.current_track_index = row_for_path(table, playing)
        self.save_state()
