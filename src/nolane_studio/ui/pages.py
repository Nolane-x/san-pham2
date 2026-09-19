from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ..ai.object_voice import ObjectVoiceAnalyzer, merge_analysis_metadata
from ..image_generation import ImageGenerationService
from ..providers.registry import ProviderRegistry
from ..readable_labels import (
    sync_readable_label_objects,
    validate_readable_label_metadata,
    validate_readable_label_object_state,
)
from ..render.project_export import (
    ProjectSceneExporter,
    UnsupportedProjectTimeline,
    validate_persisted_scene_edits,
)
from ..render.scene_plan import build_scene_render_plan
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

        self.generate_image_button = QPushButton("Generate image")
        self.generate_image_button.setToolTip(
            "Generate a visual for the selected scene from its hardened image prompt"
        )
        self.generate_image_button.clicked.connect(self._generate_selected_image)
        self.generate_all_images_button = QPushButton("Generate All Images")
        self.generate_all_images_button.setToolTip(
            "Generate or reuse a cached visual for every scene"
        )
        self.generate_all_images_button.clicked.connect(self._generate_all_images)

        self.ai_analyze_button = QPushButton("AI Analyze")
        self.ai_analyze_button.setToolTip("Analyze the selected scene image + narration")
        self.ai_analyze_button.clicked.connect(self._analyze_selected_scene)
        self.analyze_all_button = QPushButton("Analyze All")
        self.analyze_all_button.setToolTip(
            "Analyze every scene that has image + narration audio"
        )
        self.analyze_all_button.clicked.connect(self._analyze_all_scenes)
        insert_at = max(0, self.toolbar_layout.count() - 2)
        self.toolbar_layout.insertWidget(insert_at, self.generate_image_button)
        self.toolbar_layout.insertWidget(insert_at + 1, self.generate_all_images_button)
        self.toolbar_layout.insertWidget(insert_at + 2, self.ai_analyze_button)
        self.toolbar_layout.insertWidget(insert_at + 3, self.analyze_all_button)

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

        self.voice_options_surface = Surface()
        voice_grid = QGridLayout(self.voice_options_surface)
        voice_grid.setContentsMargins(12, 12, 12, 12)
        voice_grid.setHorizontalSpacing(10)
        voice_grid.setVerticalSpacing(8)

        voice_grid.addWidget(QLabel("Language"), 0, 0)
        self.voice_language_edit = QLineEdit("vi-VN")
        self.voice_language_edit.setPlaceholderText("vi-VN")
        voice_grid.addWidget(self.voice_language_edit, 0, 1, 1, 2)

        voice_grid.addWidget(QLabel("Voice"), 1, 0)
        self.voice_name_combo = QComboBox()
        self.voice_name_combo.setEditable(True)
        self.voice_name_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.voice_name_combo.setPlaceholderText("Provider default")
        voice_grid.addWidget(self.voice_name_combo, 1, 1)
        self.load_voice_catalog_button = QPushButton("Load voices")
        self.load_voice_catalog_button.setObjectName("ghost")
        self.load_voice_catalog_button.clicked.connect(self._load_voice_catalog)
        voice_grid.addWidget(self.load_voice_catalog_button, 1, 2)

        voice_grid.addWidget(QLabel("Speed"), 2, 0)
        self.voice_speed_spin = QDoubleSpinBox()
        self.voice_speed_spin.setRange(0.25, 4.0)
        self.voice_speed_spin.setSingleStep(0.05)
        self.voice_speed_spin.setDecimals(2)
        self.voice_speed_spin.setValue(1.0)
        voice_grid.addWidget(self.voice_speed_spin, 2, 1, 1, 2)

        self.voice_reference_audio_label = QLabel("Reference audio")
        voice_grid.addWidget(self.voice_reference_audio_label, 3, 0)
        self.voice_reference_audio_edit = QLineEdit()
        self.voice_reference_audio_edit.setPlaceholderText("Optional voice-cloning reference")
        voice_grid.addWidget(self.voice_reference_audio_edit, 3, 1)
        self.voice_reference_audio_button = QPushButton("Browse")
        self.voice_reference_audio_button.setObjectName("ghost")
        self.voice_reference_audio_button.clicked.connect(self._browse_voice_reference_audio)
        voice_grid.addWidget(self.voice_reference_audio_button, 3, 2)

        self.voice_reference_text_label = QLabel("Reference text")
        voice_grid.addWidget(self.voice_reference_text_label, 4, 0)
        self.voice_reference_text_edit = QLineEdit()
        self.voice_reference_text_edit.setPlaceholderText("Optional transcript for the reference")
        voice_grid.addWidget(self.voice_reference_text_edit, 4, 1, 1, 2)

        self.voice_design_label = QLabel("Voice design")
        voice_grid.addWidget(self.voice_design_label, 5, 0)
        self.voice_design_edit = QLineEdit()
        self.voice_design_edit.setPlaceholderText("e.g. warm educational narrator")
        voice_grid.addWidget(self.voice_design_edit, 5, 1, 1, 2)

        self.inspector_layout.insertWidget(save_index + 2, self.voice_options_surface)
        self._sync_voice_capability_controls()

        self.transition_surface = Surface()
        transition_grid = QGridLayout(self.transition_surface)
        transition_grid.setContentsMargins(12, 12, 12, 12)
        transition_grid.setHorizontalSpacing(10)
        transition_grid.setVerticalSpacing(8)

        self.transition_pair_label = QLabel("Transition · no following scene")
        self.transition_pair_label.setObjectName("muted")
        transition_grid.addWidget(self.transition_pair_label, 0, 0, 1, 3)

        transition_grid.addWidget(QLabel("Effect"), 1, 0)
        self.transition_effect_combo = QComboBox()
        for label, effect in (
            ("Fade", "fade"),
            ("Wipe left", "wipeleft"),
            ("Wipe right", "wiperight"),
            ("Slide left", "slideleft"),
            ("Slide right", "slideright"),
            ("Smooth left", "smoothleft"),
            ("Smooth right", "smoothright"),
        ):
            self.transition_effect_combo.addItem(label, effect)
        transition_grid.addWidget(self.transition_effect_combo, 1, 1, 1, 2)

        transition_grid.addWidget(QLabel("Duration"), 2, 0)
        self.transition_duration_spin = QDoubleSpinBox()
        self.transition_duration_spin.setRange(0.1, 10.0)
        self.transition_duration_spin.setSingleStep(0.05)
        self.transition_duration_spin.setDecimals(2)
        self.transition_duration_spin.setSuffix(" s")
        self.transition_duration_spin.setValue(0.5)
        transition_grid.addWidget(self.transition_duration_spin, 2, 1, 1, 2)

        transition_actions = QHBoxLayout()
        self.transition_save_button = QPushButton("Save transition")
        self.transition_save_button.clicked.connect(self._save_selected_transition)
        self.transition_clear_button = QPushButton("Clear")
        self.transition_clear_button.setObjectName("ghost")
        self.transition_clear_button.clicked.connect(self._clear_selected_transition)
        transition_actions.addWidget(self.transition_save_button)
        transition_actions.addWidget(self.transition_clear_button)
        transition_grid.addLayout(transition_actions, 3, 0, 1, 3)

        self.inspector_layout.insertWidget(save_index + 3, self.transition_surface)

        self.scene_edit_surface = Surface()
        scene_edit_grid = QGridLayout(self.scene_edit_surface)
        scene_edit_grid.setContentsMargins(12, 10, 12, 10)
        scene_edit_grid.setHorizontalSpacing(8)
        scene_edit_grid.setVerticalSpacing(7)

        self.scene_edit_label = QLabel("Clip edit · select a scene")
        self.scene_edit_label.setObjectName("muted")
        scene_edit_grid.addWidget(self.scene_edit_label, 0, 0, 1, 8)

        self.scene_trim_start_spin = QDoubleSpinBox()
        self.scene_trim_start_spin.setRange(0.0, 1_000_000.0)
        self.scene_trim_start_spin.setDecimals(3)
        self.scene_trim_start_spin.setSingleStep(0.1)
        self.scene_trim_start_spin.setSuffix(" s")
        scene_edit_grid.addWidget(QLabel("Start"), 1, 0)
        scene_edit_grid.addWidget(self.scene_trim_start_spin, 1, 1)

        self.scene_trim_end_spin = QDoubleSpinBox()
        self.scene_trim_end_spin.setRange(0.001, 1_000_000.0)
        self.scene_trim_end_spin.setDecimals(3)
        self.scene_trim_end_spin.setSingleStep(0.1)
        self.scene_trim_end_spin.setSuffix(" s")
        scene_edit_grid.addWidget(QLabel("End"), 1, 2)
        scene_edit_grid.addWidget(self.scene_trim_end_spin, 1, 3)

        self.scene_speed_spin = QDoubleSpinBox()
        self.scene_speed_spin.setRange(0.001, 1000.0)
        self.scene_speed_spin.setDecimals(3)
        self.scene_speed_spin.setSingleStep(0.05)
        self.scene_speed_spin.setValue(1.0)
        self.scene_speed_spin.setSuffix("×")
        scene_edit_grid.addWidget(QLabel("Speed"), 1, 4)
        scene_edit_grid.addWidget(self.scene_speed_spin, 1, 5)

        self.scene_edit_save_button = QPushButton("Apply clip edit")
        self.scene_edit_save_button.clicked.connect(self._save_selected_scene_edit)
        self.scene_edit_reset_button = QPushButton("Reset")
        self.scene_edit_reset_button.setObjectName("ghost")
        self.scene_edit_reset_button.clicked.connect(self._reset_selected_scene_edit)
        scene_edit_grid.addWidget(self.scene_edit_save_button, 1, 6)
        scene_edit_grid.addWidget(self.scene_edit_reset_button, 1, 7)

        self.timeline_layout.insertWidget(1, self.scene_edit_surface)

        self.scenes.currentItemChanged.connect(
            lambda _current, _previous: self._sync_transition_editor()
        )
        self.scenes.currentItemChanged.connect(
            lambda _current, _previous: self._sync_scene_edit_editor()
        )
        self._sync_transition_editor()
        self._sync_scene_edit_editor()

    def load_project(self, project_id: str, title: str, scenes: list) -> None:
        super().load_project(project_id, title, scenes)
        self._sync_transition_editor()
        self._sync_scene_edit_editor()

    def _effective_transition_scene_ids(self) -> list[str]:
        if not self.project_id:
            return []
        scene_ids = [str(scene["id"]) for scene in self.store.list_scenes(self.project_id)]
        state = self.store.load_timeline(self.project_id)
        raw_order = state.get("mediaOrder", [])
        if (
            isinstance(raw_order, list)
            and raw_order
            and len(raw_order) == len(scene_ids)
        ):
            normalized = [str(item).strip() for item in raw_order]
            if (
                all(normalized)
                and len(set(normalized)) == len(normalized)
                and set(normalized) == set(scene_ids)
            ):
                return normalized
        return scene_ids

    def _selected_transition_pair(self) -> tuple[str, str] | None:
        selected = self._selected_scene_id()
        if not selected:
            return None
        order = self._effective_transition_scene_ids()
        try:
            index = order.index(selected)
        except ValueError:
            return None
        if index >= len(order) - 1:
            return None
        return order[index], order[index + 1]

    def _sync_transition_editor(self) -> None:
        pair = self._selected_transition_pair()
        enabled = pair is not None
        for widget in (
            self.transition_effect_combo,
            self.transition_duration_spin,
            self.transition_save_button,
            self.transition_clear_button,
        ):
            widget.setEnabled(enabled)

        if pair is None or not self.project_id:
            self.transition_pair_label.setText("Transition · no following scene")
            return

        from_id, to_id = pair
        order = self._effective_transition_scene_ids()
        from_index = order.index(from_id)
        self.transition_pair_label.setText(
            f"Transition · Scene {from_index + 1} → Scene {from_index + 2}"
        )

        existing = None
        raw_transitions = self.store.load_timeline(self.project_id).get("transitions", [])
        if isinstance(raw_transitions, list):
            for item in raw_transitions:
                if (
                    isinstance(item, dict)
                    and str(item.get("from_id", "")).strip() == from_id
                    and str(item.get("to_id", "")).strip() == to_id
                ):
                    existing = item
                    break

        effect = "fade"
        duration = 0.5
        if existing is not None:
            effect = str(existing.get("effect", "fade")).strip().lower() or "fade"
            try:
                duration = float(existing.get("duration", 0.5))
            except (TypeError, ValueError):
                duration = 0.5
        effect_index = self.transition_effect_combo.findData(effect)
        self.transition_effect_combo.setCurrentIndex(
            effect_index if effect_index >= 0 else self.transition_effect_combo.findData("fade")
        )
        self.transition_duration_spin.setValue(
            max(0.1, min(10.0, duration))
        )

    def _transition_state_for_edit(self) -> tuple[dict, list[dict]]:
        if not self.project_id:
            raise RuntimeError("No project open")
        state = self.store.load_timeline(self.project_id)
        raw = state.get("transitions", [])
        if not isinstance(raw, list):
            raise ValueError("persisted transitions must be a list")
        transitions: list[dict] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ValueError(f"persisted transition entry {index} must be a mapping")
            transitions.append(dict(item))
        return state, transitions

    def _save_selected_transition(self) -> None:
        pair = self._selected_transition_pair()
        if not self.project_id or pair is None:
            self.status_message.emit("Select a scene that has a following scene")
            return
        from_id, to_id = pair
        try:
            state, transitions = self._transition_state_for_edit()
        except ValueError as exc:
            self.status_message.emit(f"Transition state invalid · {exc}")
            return

        transitions = [
            item
            for item in transitions
            if not (
                str(item.get("from_id", "")).strip() == from_id
                and str(item.get("to_id", "")).strip() == to_id
            )
        ]
        transitions.append(
            {
                "from_id": from_id,
                "to_id": to_id,
                "effect": str(self.transition_effect_combo.currentData()),
                "duration": float(self.transition_duration_spin.value()),
            }
        )
        state["transitions"] = transitions
        self.store.save_timeline(self.project_id, state)
        self._sync_transition_editor()
        self.status_message.emit("Scene transition saved · duration remains additive")

    def _clear_selected_transition(self) -> None:
        pair = self._selected_transition_pair()
        if not self.project_id or pair is None:
            return
        from_id, to_id = pair
        try:
            state, transitions = self._transition_state_for_edit()
        except ValueError as exc:
            self.status_message.emit(f"Transition state invalid · {exc}")
            return
        state["transitions"] = [
            item
            for item in transitions
            if not (
                str(item.get("from_id", "")).strip() == from_id
                and str(item.get("to_id", "")).strip() == to_id
            )
        ]
        self.store.save_timeline(self.project_id, state)
        self._sync_transition_editor()
        self.status_message.emit("Scene transition cleared")

    def _set_scene_edit_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.scene_trim_start_spin,
            self.scene_trim_end_spin,
            self.scene_speed_spin,
            self.scene_edit_save_button,
            self.scene_edit_reset_button,
        ):
            widget.setEnabled(enabled)

    def _scene_edit_durations(self) -> dict[str, float]:
        if not self.project_id:
            return {}
        return {
            str(plan.scene_id): float(plan.total_duration)
            for plan in build_scene_render_plan(self.store, self.project_id)
        }

    def _scene_edit_state_for_edit(
        self,
    ) -> tuple[dict, list[dict], dict[str, float]]:
        if not self.project_id:
            raise RuntimeError("No project open")
        state = self.store.load_timeline(self.project_id)
        raw = state.get("sceneEdits", [])
        if not isinstance(raw, list):
            raise UnsupportedProjectTimeline("sceneEdits must be a list")
        durations = self._scene_edit_durations()
        validate_persisted_scene_edits(durations, state)
        edits: list[dict] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise UnsupportedProjectTimeline(
                    f"sceneEdits entry {index} must be a mapping"
                )
            edits.append(dict(item))
        return state, edits, durations

    def _sync_scene_edit_editor(self) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id:
            self.scene_edit_label.setText("Clip edit · select a scene")
            self._set_scene_edit_controls_enabled(False)
            return

        try:
            _state, edits, durations = self._scene_edit_state_for_edit()
        except (ValueError, UnsupportedProjectTimeline) as exc:
            self.scene_edit_label.setText(f"Clip edit · invalid timeline · {exc}")
            self._set_scene_edit_controls_enabled(False)
            return

        duration = durations.get(scene_id)
        if duration is None or duration <= 0:
            self.scene_edit_label.setText("Clip edit · invalid scene duration")
            self._set_scene_edit_controls_enabled(False)
            return

        scenes = self.store.list_scenes(self.project_id)
        try:
            scene_number = next(
                index + 1
                for index, scene in enumerate(scenes)
                if str(scene["id"]) == scene_id
            )
        except StopIteration:
            self.scene_edit_label.setText("Clip edit · selected scene missing")
            self._set_scene_edit_controls_enabled(False)
            return

        existing = next(
            (
                item
                for item in edits
                if str(item.get("scene_id", "")).strip() == scene_id
            ),
            None,
        )
        trim_start = 0.0
        trim_end = duration
        speed = 1.0
        if existing is not None:
            trim_start = float(existing["trim_start"])
            trim_end = float(existing["trim_end"])
            speed = float(existing["speed"])

        self.scene_trim_start_spin.setMaximum(duration)
        self.scene_trim_end_spin.setMaximum(duration)
        self.scene_trim_start_spin.setValue(trim_start)
        self.scene_trim_end_spin.setValue(trim_end)
        self.scene_speed_spin.setValue(speed)
        self.scene_edit_label.setText(
            f"Clip edit · Scene {scene_number} · source {duration:.2f}s"
        )
        self._set_scene_edit_controls_enabled(True)

    def _save_selected_scene_edit(self) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id:
            self.status_message.emit("Select a scene before editing its clip")
            return
        try:
            state, edits, durations = self._scene_edit_state_for_edit()
        except (ValueError, UnsupportedProjectTimeline) as exc:
            self.status_message.emit(f"Scene clip edit invalid · {exc}")
            self._sync_scene_edit_editor()
            return

        duration = durations.get(scene_id)
        if duration is None:
            self.status_message.emit("Scene clip edit invalid · selected scene missing")
            return
        trim_start = float(self.scene_trim_start_spin.value())
        trim_end = float(self.scene_trim_end_spin.value())
        speed = float(self.scene_speed_spin.value())
        candidate = [
            item
            for item in edits
            if str(item.get("scene_id", "")).strip() != scene_id
        ]
        candidate.append(
            {
                "scene_id": scene_id,
                "trim_start": trim_start,
                "trim_end": trim_end,
                "speed": speed,
            }
        )
        next_state = dict(state)
        next_state["sceneEdits"] = candidate
        try:
            validate_persisted_scene_edits(durations, next_state)
        except UnsupportedProjectTimeline as exc:
            self.status_message.emit(f"Scene clip edit invalid · {exc}")
            return

        self.store.save_timeline(self.project_id, next_state)
        self._sync_scene_edit_editor()
        effective = (trim_end - trim_start) / speed
        self.status_message.emit(
            f"Scene clip edit saved · effective duration {effective:.2f}s"
        )

    def _reset_selected_scene_edit(self) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id:
            return
        try:
            state, edits, durations = self._scene_edit_state_for_edit()
        except (ValueError, UnsupportedProjectTimeline) as exc:
            self.status_message.emit(f"Scene clip edit invalid · {exc}")
            self._sync_scene_edit_editor()
            return
        next_state = dict(state)
        next_state["sceneEdits"] = [
            item
            for item in edits
            if str(item.get("scene_id", "")).strip() != scene_id
        ]
        validate_persisted_scene_edits(durations, next_state)
        self.store.save_timeline(self.project_id, next_state)
        self._sync_scene_edit_editor()
        self.status_message.emit("Scene clip edit reset to full duration")

    def _start_task(
        self,
        task: Callable[[], object],
        *,
        started: str,
        success: Callable[[object], str],
        on_result: Callable[[object], None] | None = None,
    ) -> None:
        self.status_message.emit(started)
        worker = TaskWorker(task, self)
        self._task_workers.append(worker)

        def done(result: object) -> None:
            if on_result is not None:
                on_result(result)
            self.status_message.emit(success(result))
            self._refresh_media()
            scene_id = self._selected_scene_id()
            if scene_id:
                self._refresh_scenes(
                    selected_id=scene_id,
                    fallback_row=self.scenes.currentRow(),
                )
                self._refresh_canvas_objects()

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
        self._sync_object_timing_editor()

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

    def _image_service(self) -> ImageGenerationService:
        return ImageGenerationService(
            self.store,
            self.providers,
            Path(self.store.db_path).parent / "generated",
        )

    def _generate_selected_image(self) -> None:
        if not self.project_id:
            self.status_message.emit("Open a project before generating an image")
            return
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene first")
            return
        try:
            provider_name = self._provider_name("image")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        project_id = self.project_id
        service = self._image_service()
        self._start_task(
            lambda: service.generate_scene(
                project_id,
                scene_id,
                provider_name=provider_name,
            ),
            started="Generating selected scene image…",
            success=lambda artifact: f"Image ready · {Path(artifact.path).name}",
        )

    def _generate_all_images(self) -> None:
        if not self.project_id:
            self.status_message.emit("Open a project before generating images")
            return
        try:
            provider_name = self._provider_name("image")
        except RuntimeError as exc:
            self.status_message.emit(str(exc))
            return
        project_id = self.project_id
        service = self._image_service()
        self._start_task(
            lambda: service.generate_project(
                project_id,
                provider_name=provider_name,
            ),
            started="Generate All Images · processing project scenes…",
            success=lambda artifacts: (
                f"Generate All Images complete · {len(artifacts)} scene(s)"
            ),
        )

    def _voice_descriptor(self):
        matches = self.providers.find(tts=True)
        return matches[0] if matches else None

    def _sync_voice_capability_controls(self) -> None:
        descriptor = self._voice_descriptor()
        capabilities = descriptor.capabilities if descriptor is not None else None
        clone_enabled = bool(capabilities and capabilities.clone)
        design_enabled = bool(capabilities and capabilities.design)
        catalog_enabled = bool(capabilities and capabilities.list_voices)

        for widget in (
            self.voice_reference_audio_label,
            self.voice_reference_audio_edit,
            self.voice_reference_audio_button,
            self.voice_reference_text_label,
            self.voice_reference_text_edit,
        ):
            widget.setHidden(not clone_enabled)
        for widget in (self.voice_design_label, self.voice_design_edit):
            widget.setHidden(not design_enabled)
        self.load_voice_catalog_button.setHidden(not catalog_enabled)

    @staticmethod
    def _optional_voice_text(value: str) -> str | None:
        normalized = str(value).strip()
        return normalized or None

    def _voice_generation_options(self) -> dict[str, object]:
        return {
            "language": self.voice_language_edit.text().strip() or "vi-VN",
            "voice": self._optional_voice_text(self.voice_name_combo.currentText()),
            "speed": float(self.voice_speed_spin.value()),
            "reference_audio": self._optional_voice_text(
                self.voice_reference_audio_edit.text()
            ),
            "reference_text": self._optional_voice_text(
                self.voice_reference_text_edit.text()
            ),
            "design_instructions": self._optional_voice_text(
                self.voice_design_edit.text()
            ),
        }

    def _browse_voice_reference_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select reference voice audio",
            "",
            "Audio (*.wav *.mp3 *.m4a *.flac *.ogg);;All files (*)",
        )
        if path:
            self.voice_reference_audio_edit.setText(path)

    def _apply_voice_catalog(self, result: object) -> None:
        voices = [str(item).strip() for item in list(result) if str(item).strip()]
        current = self.voice_name_combo.currentText().strip()
        self.voice_name_combo.clear()
        self.voice_name_combo.addItems(voices)
        if current:
            self.voice_name_combo.setEditText(current)

    def _load_voice_catalog(self) -> None:
        descriptor = self._voice_descriptor()
        if descriptor is None:
            self.status_message.emit("No TTS provider configured. Open Providers first.")
            return
        if not descriptor.capabilities.list_voices:
            self.status_message.emit("Selected voice provider does not expose a voice catalog")
            return
        service = self._voice_service()
        provider_name = descriptor.name
        self._start_task(
            lambda: service.list_voices(provider_name),
            started="Loading provider voice catalog…",
            success=lambda voices: f"Loaded {len(voices)} voice(s)",
            on_result=self._apply_voice_catalog,
        )

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
        voice_options = self._voice_generation_options()
        self._start_task(
            lambda: service.synthesize_scene(
                project_id,
                scene_id,
                provider_name=provider_name,
                **voice_options,
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
        voice_options = self._voice_generation_options()
        self._start_task(
            lambda: service.synthesize_project(
                project_id,
                provider_name=provider_name,
                **voice_options,
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
        validate_readable_label_metadata(metadata)
        validate_readable_label_object_state(self.store, scene_id)
        self.store.update_scene(scene_id, metadata=metadata)
        sync_readable_label_objects(self.store, scene_id, metadata)
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
