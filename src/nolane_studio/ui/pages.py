from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

from ..render.project_export import ProjectSceneExporter
from ..storage.store import ProjectStore
from .pages_base import *  # noqa: F401,F403 - compatibility facade for existing page API
from .pages_base import StudioPage as _BaseStudioPage


class ExportWorker(QThread):
    """Export one persisted project without flattening the editor into loose media."""

    completed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        store: ProjectStore,
        project_id: str,
        output_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.store = store
        self.project_id = str(project_id)
        self.output_path = str(output_path)

    def run(self) -> None:
        try:
            ProjectSceneExporter(self.store).export(self.project_id, self.output_path)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(self.output_path)


class StudioPage(_BaseStudioPage):
    """Studio page whose export path is authoritative scene/canvas state."""

    def _export_media(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before exporting")
            return
        if not self.store.list_scenes(self.project_id):
            self.status_message.emit("Add at least one scene before exporting")
            return

        output, _ = QFileDialog.getSaveFileName(
            self,
            "Export video",
            "NolaneStudio-export.mp4",
            "MP4 video (*.mp4)",
        )
        if not output:
            return
        if not output.lower().endswith(".mp4"):
            output += ".mp4"

        self.export_button.setEnabled(False)
        self.export_button.setText("Exporting…")
        self.status_message.emit(
            "Export started · rendering persisted scene canvas in project order"
        )
        self._export_worker = ExportWorker(self.store, self.project_id, output, self)
        self._export_worker.completed.connect(self._export_complete)
        self._export_worker.failed.connect(self._export_failed)
        self._export_worker.start()
