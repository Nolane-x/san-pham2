from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from ..ai.object_voice import ObjectVoiceAnalyzer, merge_analysis_metadata
from ..providers.registry import ProviderRegistry
from ..render.project_export import ProjectSceneExporter
from ..storage.store import ProjectStore
from ..voice import VoiceFromContentService
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


class TaskWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, task: Callable[[], object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        try:
            result = self.task()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(result)


class StudioPage(_BaseStudioPage):
    """Studio page whose canvas, AI Analyze and voice flows use persisted state."""

    def __init__(
        self,
        store: ProjectStore,
        parent: QWidget | None = None,
        *,
        providers: ProviderRegistry | None = None,
    ) -> None:
        super().__init__(store, parent)
        self.providers = providers or ProviderRegistry()
        self._task_workers: list[TaskWorker] = []

        self.ai_analyze_button = QPushButton("AI Analyze")
        self.ai_analyze_button.setToolTip("Analyze the selected scene image + narration")
        self.ai_analyze_button.clicked.connect(self._analyze_selected_scene)
        self.analyze_all_button = QPushButton("Analyze All")
        self.analyze_all_button.setToolTip(
            "Analyze every scene that has image + narration audio"
        )
        self.analyze_all_button.clicked.connect(self._analyze_all_scenes)
        insert_at = max(0, self.toolbar_layout.count() - 2)
        self.toolbar_layout.insertWidget(insert_at, self.ai_analyze_button)
        self.toolbar_layout.insertWidget(insert_at + 1, self.analyze_all_button)

        self.attach_media_button = QPushButton("Attach")
        self.attach_media_button.setObjectName("ghost")
        self.attach_media_button.setToolTip(
            "Attach selected image/audio/video to the selected scene"
        )
        self.attach_media_button.clicked.connect(self._attach_selected_media)
        self.media_header_layout.insertWidget(
            max(0, self.media_header_layout.count() - 1),
            self.attach_media_button,
        )

        voice_actions = QHBoxLayout()
        self.generate_voice_button = QPushButton("Generate voice")
        self.generate_voice_button.clicked.connect(self._generate_selected_voice)
        self.voice_from_content_button = QPushButton("Voice From Content")
        self.voice_from_content_button.clicked.connect(self._voice_from_content)
        voice_actions.addWidget(self.generate_voice_button)
        voice_actions.addWidget(self.voice_from_content_button)
        save_index = self.inspector_layout.indexOf(self.save_scene_button)
        self.inspector_layout.insertLayout(save_index + 1, voice_actions)

    def _start_task(
        self,
        task: Callable[[], object],
        *,
        started: str,
        success: Callable[[object], str],
    ) -> None:
        self.status_message.emit(started)
        worker = TaskWorker(task, self)
        self._task_workers.append(worker)

        def done(result: object) -> None:
            self.status_message.emit(success(result))
            self._refresh_media()
            scene_id = self._selected_scene_id()
            if scene_id:
                self._refresh_scenes(
                    selected_id=scene_id,
                    fallback_row=self.scenes.currentRow(),
                )

        def failed(message: str) -> None:
            self.status_message.emit(f"Operation failed · {message}")

        def cleanup() -> None:
            if worker in self._task_workers:
                self._task_workers.remove(worker)

        worker.completed.connect(done)
        worker.failed.connect(failed)
        worker.finished.connect(cleanup)
        worker.start()

    def _provider_name(self, capability: str) -> str:
        matches = self.providers.find(**{capability: True})
        if not matches:
            raise RuntimeError(
                f"No {capability.upper()} provider configured. Open Providers first."
            )
        return matches[0].name

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

    def _attach_selected_media(self) -> None:
        if not self.project_id:
            return
        scene_id = self._selected_scene_id()
        item = self.media_list.currentItem()
        if not scene_id or item is None:
            self.status_message.emit("Select both a scene and a media item first")
            return
        media_id = item.data(Qt.ItemDataRole.UserRole)
        media = next(
            (
                row
                for row in self.store.list_media(self.project_id)
                if row["id"] == media_id
            ),
            None,
        )
        scene = self._scene_by_id(scene_id)
        if media is None or scene is None:
            return
        metadata = dict(scene.get("metadata") or {})
        if media["kind"] == "image":
            metadata.update(
                {"visual_media_id": media["id"], "visual_path": media["file_path"]}
            )
        elif media["kind"] == "audio":
            metadata.update(
                {"voice_media_id": media["id"], "voice_path": media["file_path"]}
            )
        else:
            metadata.update(
                {
                    "source_video_media_id": media["id"],
                    "source_video_path": media["file_path"],
                }
            )
        self.store.update_scene(scene_id, metadata=metadata)
        self.status_message.emit(f"Attached {media['kind']} to selected scene")

    def _voice_service(self) -> VoiceFromContentService:
        return VoiceFromContentService(
            self.store,
            self.providers,
            Path(self.store.db_path).parent / "generated",
        )

    def _generate_selected_voice(self) -> None:
        if not self.project_id:
            self.status_message.emit("Open a project before generating voice")
            return
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene first")
            return
        try:
            provider_name = self._provider_name("tts")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        project_id = self.project_id
        service = self._voice_service()
        self._start_task(
            lambda: service.synthesize_scene(
                project_id,
                scene_id,
                provider_name=provider_name,
            ),
            started="Generating selected scene voice…",
            success=lambda artifact: f"Voice ready · {Path(artifact.path).name}",
        )

    def _voice_from_content(self) -> None:
        if not self.project_id:
            self.status_message.emit("Open a project before generating voice")
            return
        try:
            provider_name = self._provider_name("tts")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        project_id = self.project_id
        service = self._voice_service()
        self._start_task(
            lambda: service.synthesize_project(
                project_id,
                provider_name=provider_name,
            ),
            started="Voice From Content · generating project narration…",
            success=lambda artifacts: (
                f"Voice From Content complete · {len(artifacts)} scene(s)"
            ),
        )

    @staticmethod
    def _analysis_paths(scene: dict) -> tuple[Path, Path]:
        metadata = dict(scene.get("metadata") or {})
        image_path = metadata.get("visual_path") or metadata.get("image_path")
        voice_path = metadata.get("voice_path")
        if not image_path:
            raise ValueError("scene has no attached/generated image")
        if not voice_path:
            raise ValueError("scene has no attached/generated narration audio")
        image = Path(str(image_path))
        voice = Path(str(voice_path))
        if not image.is_file():
            raise ValueError(f"scene image is missing: {image}")
        if not voice.is_file():
            raise ValueError(f"scene narration audio is missing: {voice}")
        return image, voice

    def _analyze_scene_sync(self, scene_id: str) -> object:
        if not self.project_id:
            raise RuntimeError("No project open")
        scene = self._scene_by_id(scene_id)
        if scene is None:
            raise KeyError(scene_id)
        image_path, voice_path = self._analysis_paths(scene)
        stt_name = self._provider_name("stt")
        vision_name = self._provider_name("vision")
        analyzer = ObjectVoiceAnalyzer(
            self.providers.get(stt_name),
            self.providers.get(vision_name),
            cache_dir=Path(self.store.db_path).parent / "analysis-cache",
        )
        result = analyzer.analyze(
            scene_id=scene_id,
            image_bytes=image_path.read_bytes(),
            audio_bytes=voice_path.read_bytes(),
        )
        metadata = merge_analysis_metadata(
            scene.get("metadata"),
            result.to_metadata(),
        )
        self.store.update_scene(scene_id, metadata=metadata)
        return result

    def _analyze_selected_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene before AI Analyze")
            return
        try:
            self._provider_name("stt")
            self._provider_name("vision")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        self._start_task(
            lambda: self._analyze_scene_sync(scene_id),
            started="AI Analyze · mapping narration to visible objects…",
            success=lambda result: (
                f"AI Analyze complete · {len(result.objects)} object(s) grounded"
            ),
        )

    def _analyze_all_scenes(self) -> None:
        if not self.project_id:
            self.status_message.emit("Open a project before Analyze All")
            return
        try:
            self._provider_name("stt")
            self._provider_name("vision")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        scene_ids = [
            scene["id"] for scene in self.store.list_scenes(self.project_id)
        ]

        def task() -> tuple[int, int]:
            completed = 0
            skipped = 0
            for scene_id in scene_ids:
                try:
                    self._analyze_scene_sync(scene_id)
                except ValueError:
                    skipped += 1
                    continue
                completed += 1
            if completed == 0:
                raise ValueError("no scenes have both image and narration audio")
            return completed, skipped

        self._start_task(
            task,
            started="Analyze All · processing eligible scenes…",
            success=lambda counts: (
                f"Analyze All complete · {counts[0]} analyzed · {counts[1]} skipped"
            ),
        )

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
