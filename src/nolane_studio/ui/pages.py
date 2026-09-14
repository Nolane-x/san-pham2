from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
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
    """Studio page whose export and layer UI preserve authoritative canvas state."""

    def _refresh_canvas_objects(self, *, selected_object_id: str | None = None) -> None:
        scene_id = self._selected_scene_id()
        rows = self.store.list_visual_objects(scene_id) if scene_id else []

        # Storage and CanvasEditor use ascending z_index (back -> front). The
        # layer panel follows the conventional editor stack: frontmost first.
        self.canvas.set_objects(rows)
        panel_rows = list(reversed(rows))

        self.layers.blockSignals(True)
        self.layers.clear()
        selected_row = -1
        for row_index, obj in enumerate(panel_rows):
            z_index = int(obj.get("z_index", len(rows) - row_index - 1))
            label = obj.get("name") or f"{str(obj.get('kind', 'object')).title()} {z_index + 1}"
            self.layers.addItem(str(label))
            item = self.layers.item(row_index)
            item.setData(Qt.ItemDataRole.UserRole, obj["id"])
            if selected_object_id and obj["id"] == selected_object_id:
                selected_row = row_index
        if panel_rows:
            self.layers.setCurrentRow(selected_row if selected_row >= 0 else 0)
        self.layers.blockSignals(False)
        if panel_rows:
            self.canvas.select_object(self._selected_object_id())

    def _move_selected_object(self, delta: int) -> None:
        object_id = self._selected_object_id()
        if not object_id:
            return

        current_row = self.layers.currentRow()
        target_row = current_row + int(delta)
        count = self.layers.count()
        if target_row < 0 or target_row >= count:
            return

        # Panel rows are front -> back, whereas persisted z_index is back ->
        # front. Convert the target row instead of treating row == z_index.
        target_z_index = (count - 1) - target_row
        self.store.move_visual_object(object_id, target_z_index)
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Layer order updated")

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
