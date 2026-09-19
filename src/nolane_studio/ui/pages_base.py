from __future__ import annotations

import math
import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..ai.scenes import split_script_into_scenes
from ..config import ProviderSettings, SettingsStore
from ..render.exporter import ExportClip, MediaExporter
from ..storage.store import ProjectStore
from .design import PRODUCT_TAGLINE, ThemeTokens
from .widgets import CanvasEditor, Dot, SectionTitle, Surface


def _heading(eyebrow: str, title: str, subtitle: str) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    eye = QLabel(eyebrow.upper())
    eye.setObjectName("eyebrow")
    h = QLabel(title)
    h.setObjectName("pageTitle")
    sub = QLabel(subtitle)
    sub.setObjectName("pageSubtitle")
    sub.setWordWrap(True)
    layout.addWidget(eye)
    layout.addWidget(h)
    layout.addWidget(sub)
    return box


class ExportWorker(QThread):
    completed = Signal(str)
    failed = Signal(str)

    def __init__(self, clips: list[ExportClip], output_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.clips = clips
        self.output_path = output_path

    def run(self) -> None:
        try:
            MediaExporter().export(self.clips, self.output_path)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(self.output_path)


class CreatePage(QWidget):
    project_created = Signal(str, str, list)

    def __init__(self, store: ProjectStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self._scenes = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(38, 28, 38, 28)
        outer.setSpacing(22)
        outer.addWidget(_heading("Creator workspace", "Turn a script into a scene plan", PRODUCT_TAGLINE))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        input_surface = Surface()
        input_layout = QVBoxLayout(input_surface)
        input_layout.setContentsMargins(22, 20, 22, 20)
        input_layout.setSpacing(14)
        input_layout.addWidget(SectionTitle("Input", "Your story", "Structure stays local. Providers only enrich what you approve."))

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Project title")
        self.script_edit = QTextEdit()
        self.script_edit.setPlaceholderText(
            "Paste a script, narration, lesson, product story or any text.\n\n"
            "Nolane Studio will split it into bounded scenes locally before any API is called."
        )
        self.script_edit.setMinimumHeight(260)
        input_layout.addWidget(self.title_edit)
        input_layout.addWidget(self.script_edit, 1)

        control_row = QHBoxLayout()
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Whiteboard", "Clean editorial", "Motion collage"])
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Vietnamese", "English", "Auto"])
        control_row.addWidget(self.style_combo)
        control_row.addWidget(self.language_combo)
        control_row.addStretch(1)
        input_layout.addLayout(control_row)

        action_row = QHBoxLayout()
        manual = QPushButton("Start manually")
        manual.setToolTip("Open the studio without AI scene planning")
        manual.clicked.connect(self._create_manual)
        analyze = QPushButton("Build scene plan")
        analyze.setObjectName("primary")
        analyze.clicked.connect(self._build_scene_plan)
        action_row.addWidget(manual)
        action_row.addStretch(1)
        action_row.addWidget(analyze)
        input_layout.addLayout(action_row)

        preview_surface = Surface(raised=True)
        preview_layout = QVBoxLayout(preview_surface)
        preview_layout.setContentsMargins(18, 18, 18, 18)
        preview_layout.setSpacing(12)
        title_row = QHBoxLayout()
        title_row.addWidget(SectionTitle("Scene map", "Local plan"))
        title_row.addStretch(1)
        self.scene_count = QLabel("0 scenes")
        self.scene_count.setObjectName("chip")
        title_row.addWidget(self.scene_count)
        preview_layout.addLayout(title_row)
        self.scene_list = QListWidget()
        self.scene_list.setAlternatingRowColors(False)
        preview_layout.addWidget(self.scene_list, 1)
        note = QLabel("Tip: keep scenes short enough to visualize, but long enough to carry one idea.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        preview_layout.addWidget(note)

        splitter.addWidget(input_surface)
        splitter.addWidget(preview_surface)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([760, 420])

    def _build_scene_plan(self) -> None:
        script = self.script_edit.toPlainText().strip()
        if not script:
            self.scene_list.clear()
            self.scene_list.addItem("Paste a script first — nothing leaves your machine.")
            self.scene_count.setText("0 scenes")
            return
        self._scenes = split_script_into_scenes(script, min_words=28, max_words=48)
        self.scene_list.clear()
        for scene in self._scenes:
            excerpt = scene.text if len(scene.text) <= 115 else scene.text[:112].rstrip() + "…"
            self.scene_list.addItem(f"{scene.index + 1:02d}   {excerpt}")
        self.scene_count.setText(f"{len(self._scenes)} scenes")
        self._persist_and_emit(self._scenes)

    def _create_manual(self) -> None:
        self._persist_and_emit([])

    def _persist_and_emit(self, scenes: list) -> None:
        title = self.title_edit.text().strip() or "Untitled project"
        project_id = uuid.uuid4().hex[:12]
        self.store.create_project(project_id, title, expected_image_count=0)
        if scenes:
            self.store.replace_scenes(project_id, scenes)
        self.project_created.emit(project_id, title, scenes)


class StudioPage(QWidget):
    status_message = Signal(str)

    def __init__(self, store: ProjectStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.project_id: str | None = None
        self._export_worker: ExportWorker | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("topbar")
        tb = QHBoxLayout(toolbar)
        self.toolbar_layout = tb
        tb.setContentsMargins(20, 10, 20, 10)
        tb.setSpacing(8)
        self.project_label = QLabel("No project open")
        self.project_label.setObjectName("sectionTitle")
        tb.addWidget(self.project_label)
        status = QLabel("LOCAL-FIRST")
        status.setObjectName("chip")
        tb.addWidget(status)
        tb.addStretch(1)
        self.preview_button = QPushButton("Preview")
        self.preview_button.setToolTip("Render and play the selected scene preview")
        self.export_button = QPushButton("Export video")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self._export_media)
        tb.addWidget(self.preview_button)
        tb.addWidget(self.export_button)
        outer.addWidget(toolbar)

        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.setChildrenCollapsible(False)
        outer.addWidget(vertical, 1)

        workspace = QSplitter(Qt.Orientation.Horizontal)
        workspace.setChildrenCollapsible(False)

        scenes_panel = Surface()
        scenes_panel.setMinimumWidth(210)
        scenes_panel.setMaximumWidth(300)
        scenes_layout = QVBoxLayout(scenes_panel)
        scenes_layout.setContentsMargins(14, 14, 14, 14)
        scenes_layout.setSpacing(8)
        scenes_layout.addWidget(SectionTitle("Sequence", "Scenes"))
        self.scenes = QListWidget()
        self.scenes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scenes.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.scenes.addItem("Create a project to begin")
        self.scenes.currentItemChanged.connect(self._load_selected_scene_editor)
        scenes_layout.addWidget(self.scenes, 1)

        self.add_scene_button = QPushButton("+ Add scene")
        self.add_scene_button.clicked.connect(self._add_scene)
        scenes_layout.addWidget(self.add_scene_button)
        scene_actions = QHBoxLayout()
        scene_actions.setSpacing(5)
        self.duplicate_scene_button = QPushButton("Duplicate")
        self.duplicate_scene_button.setObjectName("ghost")
        self.duplicate_scene_button.clicked.connect(self._duplicate_selected_scene)
        self.move_scene_up_button = QPushButton("↑")
        self.move_scene_up_button.setObjectName("ghost")
        self.move_scene_up_button.setToolTip("Move selected scene up")
        self.move_scene_up_button.clicked.connect(lambda: self._move_selected_scene(-1))
        self.move_scene_down_button = QPushButton("↓")
        self.move_scene_down_button.setObjectName("ghost")
        self.move_scene_down_button.setToolTip("Move selected scene down")
        self.move_scene_down_button.clicked.connect(lambda: self._move_selected_scene(1))
        self.delete_scene_button = QPushButton("Delete")
        self.delete_scene_button.setObjectName("ghost")
        self.delete_scene_button.clicked.connect(self._delete_selected_scene)
        scene_actions.addWidget(self.duplicate_scene_button, 1)
        scene_actions.addWidget(self.move_scene_up_button)
        scene_actions.addWidget(self.move_scene_down_button)
        scene_actions.addWidget(self.delete_scene_button, 1)
        scenes_layout.addLayout(scene_actions)
        scenes_layout.addSpacing(8)

        media_header = QHBoxLayout()
        self.media_header_layout = media_header
        media_title = QLabel("Media")
        media_title.setObjectName("sectionTitle")
        media_header.addWidget(media_title)
        media_header.addStretch(1)
        import_media = QPushButton("Import")
        self.import_media_button = import_media
        import_media.setObjectName("ghost")
        import_media.clicked.connect(self._import_media)
        media_header.addWidget(import_media)
        scenes_layout.addLayout(media_header)
        self.media_list = QListWidget()
        self.media_list.setMaximumHeight(138)
        self.media_list.itemDoubleClicked.connect(self._add_media_to_canvas)
        scenes_layout.addWidget(self.media_list)

        canvas_shell = QFrame()
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(16, 16, 16, 16)
        canvas_layout.setSpacing(12)
        canvas_head = QHBoxLayout()
        canvas_head.addWidget(SectionTitle("Composition", "Canvas", "16:9 · 1280 × 720 · 24 fps"))
        canvas_head.addStretch(1)
        self.draw_button = QPushButton("Draw")
        self.draw_button.setObjectName("ghost")
        self.draw_button.setCheckable(True)
        self.draw_button.setEnabled(False)
        self.draw_button.setToolTip("Draw a persistent freehand layer on the selected scene")
        canvas_head.addWidget(self.draw_button)
        zoom = QLabel("Fit  •  100%")
        zoom.setObjectName("chip")
        canvas_head.addWidget(zoom)
        canvas_layout.addLayout(canvas_head)
        canvas_surface = Surface(raised=True)
        canvas_surface_layout = QVBoxLayout(canvas_surface)
        canvas_surface_layout.setContentsMargins(8, 8, 8, 8)
        self.canvas = CanvasEditor()
        self.canvas.object_selected.connect(self._select_object_from_canvas)
        self.canvas.object_transform_changed.connect(self._canvas_object_transform_changed)
        self.canvas.drawing_completed.connect(self._persist_freehand_drawing)
        self.draw_button.toggled.connect(self.canvas.set_drawing_enabled)
        canvas_surface_layout.addWidget(self.canvas, 1)
        canvas_layout.addWidget(canvas_surface, 1)

        inspector = Surface()
        inspector.setMinimumWidth(250)
        inspector.setMaximumWidth(330)
        inspector_layout = QVBoxLayout(inspector)
        self.inspector_layout = inspector_layout
        inspector_layout.setContentsMargins(16, 14, 16, 14)
        inspector_layout.setSpacing(10)
        inspector_layout.addWidget(SectionTitle("Selected scene", "Inspector"))

        layer_head = QHBoxLayout()
        layer_title = QLabel("Layers")
        layer_title.setObjectName("sectionTitle")
        layer_head.addWidget(layer_title)
        layer_head.addStretch(1)
        add_text = QPushButton("+ Text")
        add_text.setObjectName("ghost")
        add_text.clicked.connect(self._add_text_object)
        add_shape = QPushButton("+ Shape")
        add_shape.setObjectName("ghost")
        add_shape.clicked.connect(self._add_shape_object)
        layer_head.addWidget(add_text)
        layer_head.addWidget(add_shape)
        inspector_layout.addLayout(layer_head)
        self.layers = QListWidget()
        self.layers.setMaximumHeight(150)
        self.layers.currentItemChanged.connect(self._layer_selection_changed)
        inspector_layout.addWidget(self.layers)
        layer_actions = QHBoxLayout()
        layer_up = QPushButton("↑")
        layer_up.setObjectName("ghost")
        layer_up.setToolTip("Move layer forward")
        layer_up.clicked.connect(lambda: self._move_selected_object(-1))
        layer_down = QPushButton("↓")
        layer_down.setObjectName("ghost")
        layer_down.setToolTip("Move layer backward")
        layer_down.clicked.connect(lambda: self._move_selected_object(1))
        delete_layer = QPushButton("Delete layer")
        delete_layer.setObjectName("ghost")
        delete_layer.clicked.connect(self._delete_selected_object)
        layer_actions.addWidget(layer_up)
        layer_actions.addWidget(layer_down)
        layer_actions.addWidget(delete_layer, 1)
        inspector_layout.addLayout(layer_actions)

        tabs = QComboBox()
        tabs.addItems(["Drawing", "Motion", "Voice", "Timing"])
        inspector_layout.addWidget(tabs)

        scene_text_label = QLabel("Narration / description")
        scene_text_label.setObjectName("muted")
        inspector_layout.addWidget(scene_text_label)
        self.scene_text_edit = QTextEdit()
        self.scene_text_edit.setPlaceholderText("Select a scene to edit its narration or description")
        self.scene_text_edit.setMinimumHeight(92)
        inspector_layout.addWidget(self.scene_text_edit)
        save_scene = QPushButton("Save scene")
        self.save_scene_button = save_scene
        save_scene.setObjectName("primary")
        save_scene.clicked.connect(self._save_selected_scene)
        inspector_layout.addWidget(save_scene)

        settings_grid = QGridLayout()
        settings_grid.setContentsMargins(0, 0, 0, 0)
        settings_grid.setHorizontalSpacing(8)
        settings_grid.setVerticalSpacing(7)

        self.reveal_spin = QDoubleSpinBox()
        self.reveal_spin.setRange(0.0, 3600.0)
        self.reveal_spin.setDecimals(2)
        self.reveal_spin.setSingleStep(0.25)
        self.reveal_spin.setSuffix(" s")
        self.hold_spin = QDoubleSpinBox()
        self.hold_spin.setRange(0.0, 3600.0)
        self.hold_spin.setDecimals(2)
        self.hold_spin.setSingleStep(0.25)
        self.hold_spin.setSuffix(" s")

        self.render_style_combo = QComboBox()
        self.render_style_combo.addItem("Whiteboard", "whiteboard")
        self.render_style_combo.addItem("Color reveal", "color_reveal")
        self.visual_mode_combo = QComboBox()
        self.visual_mode_combo.addItem("Drawing", "drawing")
        self.visual_mode_combo.addItem("Camera motion", "camera_motion")
        self.brush_mode_combo = QComboBox()
        self.brush_mode_combo.addItem("Left → right", "lr")
        self.brush_mode_combo.addItem("Right → left", "rl")
        self.hand_style_combo = QComboBox()
        self.hand_style_combo.addItem("Hand 1", "hand-1.png")
        self.hand_style_combo.addItem("Hand 2", "hand-2.png")
        self.hand_style_combo.addItem("Hand 3", "hand-3.png")
        self.object_timing_combo = QComboBox()
        self.object_timing_combo.addItem("Fixed", "fixed")
        self.object_timing_combo.addItem("Custom", "custom")

        self.outro_enabled_check = QCheckBox("On")
        self.outro_enabled_check.setToolTip(
            "Recovered whiteboard outro: move the fully revealed scene left after the final hold"
        )
        self.outro_direction_combo = QComboBox()
        self.outro_direction_combo.addItem("Left", "left")
        self.outro_duration_spin = QDoubleSpinBox()
        self.outro_duration_spin.setRange(0.0, 5.0)
        self.outro_duration_spin.setDecimals(2)
        self.outro_duration_spin.setSingleStep(0.05)
        self.outro_duration_spin.setSuffix(" s")
        self.outro_controls = QWidget()
        outro_controls_layout = QHBoxLayout(self.outro_controls)
        outro_controls_layout.setContentsMargins(0, 0, 0, 0)
        outro_controls_layout.setSpacing(5)
        outro_controls_layout.addWidget(self.outro_enabled_check)
        outro_controls_layout.addWidget(self.outro_direction_combo)
        outro_controls_layout.addWidget(self.outro_duration_spin)
        self.render_style_combo.currentIndexChanged.connect(
            lambda _index: self._sync_outro_controls()
        )
        self.outro_enabled_check.toggled.connect(
            lambda _checked: self._sync_outro_controls()
        )

        controls = (
            ("Reveal", self.reveal_spin),
            ("Hold", self.hold_spin),
            ("Style", self.render_style_combo),
            ("Mode", self.visual_mode_combo),
            ("Brush", self.brush_mode_combo),
            ("Hand", self.hand_style_combo),
            ("Timing", self.object_timing_combo),
            ("Outro", self.outro_controls),
        )
        for row_index, (label, widget) in enumerate(controls):
            key = QLabel(label)
            key.setObjectName("muted")
            settings_grid.addWidget(key, row_index, 0)
            settings_grid.addWidget(widget, row_index, 1)
        inspector_layout.addLayout(settings_grid)

        self.apply_render_settings_all_button = QPushButton(
            "Apply drawing settings to all scenes"
        )
        self.apply_render_settings_all_button.setObjectName("ghost")
        self.apply_render_settings_all_button.setToolTip(
            "Apply scene-wide drawing controls to every scene while preserving object-specific timing and effects"
        )
        self.apply_render_settings_all_button.clicked.connect(
            self._apply_render_settings_to_all_scenes
        )
        inspector_layout.addWidget(self.apply_render_settings_all_button)

        self.object_timing_surface = Surface()
        timing_grid = QGridLayout(self.object_timing_surface)
        timing_grid.setContentsMargins(12, 10, 12, 10)
        timing_grid.setHorizontalSpacing(8)
        timing_grid.setVerticalSpacing(7)
        self.object_timing_object_label = QLabel("Object timing · select a layer")
        self.object_timing_object_label.setObjectName("muted")
        timing_grid.addWidget(self.object_timing_object_label, 0, 0, 1, 2)

        self.object_pause_spin = QDoubleSpinBox()
        self.object_draw_spin = QDoubleSpinBox()
        self.object_push_spin = QDoubleSpinBox()
        for spin in (self.object_pause_spin, self.object_draw_spin, self.object_push_spin):
            spin.setRange(0.0, 3600.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.05)
            spin.setSuffix(" s")
        for row_index, (label, spin) in enumerate(
            (
                ("Pause", self.object_pause_spin),
                ("Draw", self.object_draw_spin),
                ("Push", self.object_push_spin),
            ),
            start=1,
        ):
            key = QLabel(label)
            key.setObjectName("muted")
            timing_grid.addWidget(key, row_index, 0)
            timing_grid.addWidget(spin, row_index, 1)

        timing_actions = QHBoxLayout()
        self.save_object_timing_button = QPushButton("Apply timing")
        self.save_object_timing_button.clicked.connect(self._save_selected_object_timing)
        self.reset_object_timing_button = QPushButton("Use default")
        self.reset_object_timing_button.setObjectName("ghost")
        self.reset_object_timing_button.clicked.connect(self._reset_selected_object_timing)
        timing_actions.addWidget(self.save_object_timing_button)
        timing_actions.addWidget(self.reset_object_timing_button)
        timing_grid.addLayout(timing_actions, 4, 0, 1, 2)
        inspector_layout.addWidget(self.object_timing_surface)
        self.object_timing_combo.currentIndexChanged.connect(
            lambda _index: self._sync_object_timing_editor()
        )

        self.remove_background_check = QCheckBox("Remove image background")
        self.auto_object_fx_check = QCheckBox("Auto object sound FX")
        inspector_layout.addWidget(self.remove_background_check)
        inspector_layout.addWidget(self.auto_object_fx_check)
        inspector_layout.addStretch(1)
        self.reset_scene_button = QPushButton("Reset scene")
        self.reset_scene_button.setToolTip(
            "Restore scene render/motion controls to defaults without deleting layers, text, media or narration"
        )
        self.reset_scene_button.clicked.connect(self._reset_selected_scene)
        inspector_layout.addWidget(self.reset_scene_button)

        workspace.addWidget(scenes_panel)
        workspace.addWidget(canvas_shell)
        workspace.addWidget(inspector)
        workspace.setStretchFactor(0, 0)
        workspace.setStretchFactor(1, 1)
        workspace.setStretchFactor(2, 0)
        workspace.setSizes([260, 735, 285])

        timeline = Surface()
        timeline.setMinimumHeight(220)
        timeline_layout = QVBoxLayout(timeline)
        self.timeline_layout = timeline_layout
        timeline_layout.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        top.addWidget(SectionTitle("Assembly", "Timeline"))
        top.addStretch(1)
        duration = QLabel("00:00 / 00:00")
        duration.setObjectName("chip")
        top.addWidget(duration)
        timeline_layout.addLayout(top)
        self.timeline_track = QHBoxLayout()
        timeline_layout.addLayout(self.timeline_track)
        self._rebuild_timeline(1)

        vertical.addWidget(workspace)
        vertical.addWidget(timeline)
        vertical.setStretchFactor(0, 1)
        vertical.setStretchFactor(1, 0)
        vertical.setSizes([570, 230])

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_render_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.reveal_spin,
            self.hold_spin,
            self.render_style_combo,
            self.visual_mode_combo,
            self.brush_mode_combo,
            self.hand_style_combo,
            self.outro_enabled_check,
            self.outro_direction_combo,
            self.outro_duration_spin,
            self.remove_background_check,
            self.auto_object_fx_check,
            self.object_timing_combo,
            self.apply_render_settings_all_button,
            self.reset_scene_button,
        ):
            widget.setEnabled(enabled)
        self._sync_object_timing_editor()
        self._sync_outro_controls()

    def _sync_outro_controls(self) -> None:
        base_enabled = self.render_style_combo.isEnabled()
        is_whiteboard = self.render_style_combo.currentData() == "whiteboard"
        enabled = base_enabled and is_whiteboard
        self.outro_enabled_check.setEnabled(enabled)
        detail_enabled = enabled and self.outro_enabled_check.isChecked()
        self.outro_direction_combo.setEnabled(detail_enabled)
        self.outro_duration_spin.setEnabled(detail_enabled)
        if is_whiteboard:
            self.outro_enabled_check.setToolTip(
                "Recovered whiteboard outro: move the fully revealed scene left after the final hold"
            )
        else:
            self.outro_enabled_check.setToolTip(
                "Outro rendering is currently verified only for whiteboard scenes"
            )

    def _load_render_controls(self, scene_id: str) -> None:
        settings = self.store.get_scene_render_settings(scene_id)
        self.reveal_spin.setValue(float(settings["reveal_duration"]))
        self.hold_spin.setValue(float(settings["hold_duration"]))
        self._set_combo_data(self.render_style_combo, settings["style"])
        self._set_combo_data(self.visual_mode_combo, settings["visual_mode"])
        self._set_combo_data(self.brush_mode_combo, settings["brush_mode"])
        self._set_combo_data(self.hand_style_combo, settings["hand_style"])
        self.outro_enabled_check.setChecked(bool(settings["outro_enabled"]))
        outro_direction = str(settings.get("outro_direction", "left") or "left").strip()
        self.outro_direction_combo.clear()
        self.outro_direction_combo.addItem("Left", "left")
        if outro_direction != "left":
            self.outro_direction_combo.addItem(
                f"Unsupported · {outro_direction}",
                outro_direction,
            )
        self._set_combo_data(self.outro_direction_combo, outro_direction)
        self.outro_duration_spin.setValue(float(settings["outro_duration"]))
        self.remove_background_check.setChecked(bool(settings["remove_background_enabled"]))
        self.auto_object_fx_check.setChecked(bool(settings["auto_object_fx_enabled"]))
        self._set_combo_data(self.object_timing_combo, settings["object_timing_mode"])
        self._set_render_controls_enabled(True)
        self._sync_object_timing_editor()
        self._sync_outro_controls()

    def _rebuild_timeline(self, scene_count: int) -> None:
        while self.timeline_track.count():
            item = self.timeline_track.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        widths = (2, 3, 2, 4)
        for i in range(max(1, scene_count)):
            clip = QFrame()
            clip.setObjectName("surfaceRaised")
            clip.setMinimumHeight(48)
            clip_l = QHBoxLayout(clip)
            clip_l.setContentsMargins(10, 0, 10, 0)
            clip_l.addWidget(Dot("#8B7CFF" if i % 2 == 0 else "#4ED7C5"))
            label = QLabel(f"Scene {i + 1}")
            label.setStyleSheet("font-weight:650;color:#DCE2ED")
            clip_l.addWidget(label)
            self.timeline_track.addWidget(clip, widths[i % len(widths)])

    def _selected_scene_id(self) -> str | None:
        item = self.scenes.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _scene_by_id(self, scene_id: str | None) -> dict | None:
        if not self.project_id or not scene_id:
            return None
        return next((scene for scene in self.store.list_scenes(self.project_id) if scene["id"] == scene_id), None)

    def _selected_object_id(self) -> str | None:
        item = self.layers.currentItem()
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    def _refresh_scenes(self, *, selected_id: str | None = None, fallback_row: int = 0) -> None:
        if not self.project_id:
            return
        rows = self.store.list_scenes(self.project_id)
        self.scenes.blockSignals(True)
        self.scenes.clear()
        selected_row = -1
        for row_index, scene in enumerate(rows):
            excerpt = scene["text"] if len(scene["text"]) <= 58 else scene["text"][:55].rstrip() + "…"
            self.scenes.addItem(f"{row_index + 1:02d}  {excerpt}")
            item = self.scenes.item(row_index)
            item.setData(Qt.ItemDataRole.UserRole, scene["id"])
            if selected_id and scene["id"] == selected_id:
                selected_row = row_index
        if rows:
            if selected_row < 0:
                selected_row = max(0, min(int(fallback_row), len(rows) - 1))
            self.scenes.setCurrentRow(selected_row)
        self.scenes.blockSignals(False)
        self._rebuild_timeline(len(rows))
        self._load_selected_scene_editor(self.scenes.currentItem(), None)

    def _load_selected_scene_editor(self, current, previous) -> None:
        del previous
        if current is None:
            self.draw_button.setChecked(False)
            self.draw_button.setEnabled(False)
            self.scene_text_edit.clear()
            self.scene_text_edit.setEnabled(False)
            self._set_render_controls_enabled(False)
            self._refresh_canvas_objects()
            return
        scene = self._scene_by_id(current.data(Qt.ItemDataRole.UserRole))
        if scene is None:
            self.draw_button.setChecked(False)
            self.draw_button.setEnabled(False)
            self.scene_text_edit.clear()
            self.scene_text_edit.setEnabled(False)
            self._set_render_controls_enabled(False)
            self._refresh_canvas_objects()
            return
        self.draw_button.setEnabled(True)
        self.scene_text_edit.setEnabled(True)
        self.scene_text_edit.setPlainText(scene["text"])
        self._load_render_controls(scene["id"])
        self._refresh_canvas_objects()

    def _refresh_canvas_objects(self, *, selected_object_id: str | None = None) -> None:
        scene_id = self._selected_scene_id()
        rows = self.store.list_visual_objects(scene_id) if scene_id else []
        self.canvas.set_objects(rows)
        self.layers.blockSignals(True)
        self.layers.clear()
        selected_row = -1
        for row_index, obj in enumerate(rows):
            label = obj.get("name") or f"{str(obj.get('kind', 'object')).title()} {row_index + 1}"
            self.layers.addItem(str(label))
            item = self.layers.item(row_index)
            item.setData(Qt.ItemDataRole.UserRole, obj["id"])
            if selected_object_id and obj["id"] == selected_object_id:
                selected_row = row_index
        if rows:
            self.layers.setCurrentRow(selected_row if selected_row >= 0 else 0)
        self.layers.blockSignals(False)
        if rows:
            self.canvas.select_object(self._selected_object_id())
        self._sync_object_timing_editor()

    def _layer_selection_changed(self, current, previous) -> None:
        del previous
        if current is None:
            self.canvas.select_object(None)
            self._sync_object_timing_editor()
            return
        value = current.data(Qt.ItemDataRole.UserRole)
        self.canvas.select_object(str(value) if value else None)
        self._sync_object_timing_editor()

    def _select_object_from_canvas(self, object_id: str) -> None:
        for row in range(self.layers.count()):
            item = self.layers.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == object_id:
                if self.layers.currentRow() != row:
                    self.layers.setCurrentRow(row)
                return

    def _object_timing_context(self):
        scene_id = self._selected_scene_id()
        object_id = self._selected_object_id()
        if not scene_id or not object_id:
            return None
        objects = self.store.list_visual_objects(scene_id)
        selected = next((obj for obj in objects if str(obj.get("id")) == object_id), None)
        if selected is None or not bool(selected.get("visible", True)):
            return None
        settings = self.store.get_scene_render_settings(scene_id)
        visible = [obj for obj in objects if bool(obj.get("visible", True))]
        fallback_draw = (
            float(settings["reveal_duration"]) / len(visible)
            if visible
            else 0.0
        )
        custom = settings.get("custom_object_timing_config") or []
        entry = None
        if isinstance(custom, list):
            for candidate in custom:
                if not isinstance(candidate, dict):
                    continue
                candidate_id = str(
                    candidate.get("object_id") or candidate.get("id") or ""
                ).strip()
                if candidate_id == object_id:
                    entry = candidate
                    break
        return scene_id, object_id, selected, settings, fallback_draw, entry

    def _sync_object_timing_editor(self) -> None:
        if not hasattr(self, "object_timing_surface"):
            return
        custom_mode = self.object_timing_combo.currentData() == "custom"
        self.object_timing_surface.setVisible(custom_mode)
        context = self._object_timing_context() if custom_mode else None
        enabled = context is not None
        for widget in (
            self.object_pause_spin,
            self.object_draw_spin,
            self.object_push_spin,
            self.save_object_timing_button,
            self.reset_object_timing_button,
        ):
            widget.setEnabled(enabled)

        if not custom_mode:
            self.object_timing_object_label.setText(
                "Object timing · switch Timing to Custom"
            )
            return
        if context is None:
            self.object_timing_object_label.setText(
                "Object timing · select a visible layer"
            )
            return

        _scene_id, _object_id, selected, _settings, fallback_draw, entry = context
        self.object_timing_object_label.setText(
            f"Object timing · {selected.get('name') or selected.get('kind') or 'Layer'}"
        )
        entry = entry or {}
        self.object_pause_spin.setValue(float(entry.get("pause", 0.0) or 0.0))
        self.object_draw_spin.setValue(
            float(entry.get("draw", fallback_draw) if entry.get("draw") is not None else fallback_draw)
        )
        self.object_push_spin.setValue(float(entry.get("push", 0.0) or 0.0))

    @staticmethod
    def _timing_push_activation(
        entries: object,
        visible_object_ids: set[str],
    ) -> bool | None:
        """Return whether visible custom timing contains positive recovered push.

        None means the persisted timing shape is ambiguous or malformed, so
        the UI preserves the existing push-enable flag instead of guessing.
        """
        if not isinstance(entries, list):
            return None
        positive = False
        for raw in entries:
            if not isinstance(raw, dict):
                return None
            object_id_value = str(raw.get("object_id") or "").strip()
            id_value = str(raw.get("id") or "").strip()
            if object_id_value and id_value and object_id_value != id_value:
                return None
            object_id = object_id_value or id_value
            if not object_id:
                return None
            if object_id not in visible_object_ids:
                continue

            values: list[float] = []
            for key in ("push", "push_seconds", "push_duration"):
                if key not in raw:
                    continue
                try:
                    number = float(raw.get(key))
                except (TypeError, ValueError):
                    return None
                if not math.isfinite(number):
                    return None
                values.append(max(0.0, number))
            if not values:
                continue
            canonical = values[0]
            if any(
                not math.isclose(value, canonical, rel_tol=1e-12, abs_tol=1e-12)
                for value in values[1:]
            ):
                return None
            if canonical > 0:
                positive = True
        return positive

    def _save_selected_object_timing(self) -> None:
        context = self._object_timing_context()
        if context is None:
            self.status_message.emit("Select a visible layer before editing timing")
            return
        scene_id, object_id, _selected, settings, _fallback_draw, _entry = context
        canonical = {
            "object_id": object_id,
            "pause": float(self.object_pause_spin.value()),
            "draw": float(self.object_draw_spin.value()),
            "push": float(self.object_push_spin.value()),
        }
        existing = settings.get("custom_object_timing_config") or []
        updated = []
        replaced = False
        if isinstance(existing, list):
            for raw in existing:
                if not isinstance(raw, dict):
                    updated.append(raw)
                    continue
                raw_id = str(raw.get("object_id") or raw.get("id") or "").strip()
                if raw_id == object_id:
                    if not replaced:
                        updated.append(canonical)
                        replaced = True
                    continue
                updated.append(dict(raw))
        if not replaced:
            updated.append(canonical)

        self._set_combo_data(self.object_timing_combo, "custom")
        visible_object_ids = {
            str(obj["id"]).strip()
            for obj in self.store.list_visual_objects(scene_id)
            if bool(obj.get("visible", True)) and str(obj.get("id", "")).strip()
        }
        push_enabled = self._timing_push_activation(updated, visible_object_ids)
        timing_settings = {
            "object_timing_mode": "custom",
            "custom_object_timing_config": updated,
        }
        if push_enabled is not None:
            timing_settings["large_object_push_enabled"] = push_enabled
        self.store.update_scene_render_settings(
            scene_id,
            reveal_duration=self.reveal_spin.value(),
            hold_duration=self.hold_spin.value(),
            settings=timing_settings,
        )
        self._sync_object_timing_editor()
        self.status_message.emit("Object timing saved")

    def _reset_selected_object_timing(self) -> None:
        context = self._object_timing_context()
        if context is None:
            self.status_message.emit("Select a visible layer before resetting timing")
            return
        scene_id, object_id, _selected, settings, _fallback_draw, _entry = context
        existing = settings.get("custom_object_timing_config") or []
        updated = []
        if isinstance(existing, list):
            for raw in existing:
                if not isinstance(raw, dict):
                    updated.append(raw)
                    continue
                raw_id = str(raw.get("object_id") or raw.get("id") or "").strip()
                if raw_id != object_id:
                    updated.append(dict(raw))
        visible_object_ids = {
            str(obj["id"]).strip()
            for obj in self.store.list_visual_objects(scene_id)
            if bool(obj.get("visible", True)) and str(obj.get("id", "")).strip()
        }
        push_enabled = self._timing_push_activation(updated, visible_object_ids)
        timing_settings = {
            "object_timing_mode": "custom",
            "custom_object_timing_config": updated,
        }
        if push_enabled is not None:
            timing_settings["large_object_push_enabled"] = push_enabled
        self.store.update_scene_render_settings(
            scene_id,
            reveal_duration=self.reveal_spin.value(),
            hold_duration=self.hold_spin.value(),
            settings=timing_settings,
        )
        self._sync_object_timing_editor()
        self.status_message.emit("Object timing reset to scene default")

    def load_project(self, project_id: str, title: str, scenes: list) -> None:
        self.project_id = project_id
        self.project_label.setText(title)
        persisted = self.store.list_scenes(project_id)
        if not persisted and scenes:
            self.store.replace_scenes(project_id, scenes)
            persisted = self.store.list_scenes(project_id)
        if not persisted:
            items = self.store.list_items(project_id)
            if items:
                for item in items:
                    self.store.add_scene(project_id, item["original_filename"])
            else:
                self.store.add_scene(project_id, "Blank scene")
        self._refresh_scenes(fallback_row=0)
        self._refresh_media()

    def _scene_mutation_timeline_state(self) -> dict:
        """Preflight timeline state before a scene lifecycle mutation.

        Non-empty legacy clip buckets remain intentionally opaque. Mutating the
        scene graph while those tracks are present could orphan or silently
        retarget recovered state, so scene lifecycle actions fail closed.
        """
        if not self.project_id:
            raise ValueError("no project is open")
        state = self.store.load_timeline(self.project_id)
        clips = state.get("clips", {})
        video_clips = state.get("videoClips", [])
        audio_clips = state.get("audioClips", [])
        media_order = state.get("mediaOrder", [])
        transitions = state.get("transitions", [])
        scene_edits = state.get("sceneEdits", [])

        if not isinstance(clips, dict):
            raise ValueError("legacy clips state must be a mapping")
        if not isinstance(video_clips, list):
            raise ValueError("legacy videoClips state must be a list")
        if not isinstance(audio_clips, list):
            raise ValueError("legacy audioClips state must be a list")
        if clips or video_clips or audio_clips:
            raise ValueError(
                "legacy timeline tracks are present and their mutation semantics are unrecovered"
            )
        if not isinstance(media_order, list):
            raise ValueError("mediaOrder must be a list")
        if not isinstance(transitions, list):
            raise ValueError("transitions must be a list")
        if not isinstance(scene_edits, list):
            raise ValueError("sceneEdits must be a list")

        scene_ids = [
            str(scene["id"]).strip()
            for scene in self.store.list_scenes(self.project_id)
        ]
        if any(not scene_id for scene_id in scene_ids) or len(set(scene_ids)) != len(scene_ids):
            raise ValueError("project scene ids must be non-blank and unique")

        effective_order = scene_ids
        if media_order:
            normalized_order = [str(item).strip() for item in media_order]
            if (
                any(not scene_id for scene_id in normalized_order)
                or len(normalized_order) != len(scene_ids)
                or len(set(normalized_order)) != len(normalized_order)
                or set(normalized_order) != set(scene_ids)
            ):
                raise ValueError("mediaOrder must be an exact permutation before scene mutation")
            effective_order = normalized_order

        adjacent = set(zip(effective_order, effective_order[1:]))
        seen_transitions: set[tuple[str, str]] = set()
        for index, item in enumerate(transitions):
            if not isinstance(item, dict):
                raise ValueError(f"transition entry {index} must be a mapping")
            from_id = str(item.get("from_id", "")).strip()
            to_id = str(item.get("to_id", "")).strip()
            pair = (from_id, to_id)
            if not from_id or not to_id:
                raise ValueError(f"transition entry {index} ids must not be blank")
            if pair not in adjacent:
                raise ValueError(
                    f"transition entry {index} must reference adjacent scenes before mutation"
                )
            if pair in seen_transitions:
                raise ValueError(f"transition entry {index} duplicates an existing pair")
            seen_transitions.add(pair)

        seen_edits: set[str] = set()
        scene_id_set = set(scene_ids)
        for index, item in enumerate(scene_edits):
            if not isinstance(item, dict):
                raise ValueError(f"sceneEdits entry {index} must be a mapping")
            scene_id = str(item.get("scene_id", "")).strip()
            if not scene_id:
                raise ValueError(f"sceneEdits entry {index} scene_id must not be blank")
            if scene_id not in scene_id_set:
                raise ValueError(
                    f"sceneEdits entry {index} references unknown scene: {scene_id}"
                )
            if scene_id in seen_edits:
                raise ValueError(f"sceneEdits contains duplicate scene_id: {scene_id}")
            seen_edits.add(scene_id)
        return dict(state)

    def _reconcile_scene_mutation_timeline(
        self,
        state: dict,
        *,
        clone_scene_edit: tuple[str, str] | None = None,
    ) -> None:
        if not self.project_id:
            return
        scene_ids = [
            str(scene["id"]).strip()
            for scene in self.store.list_scenes(self.project_id)
        ]
        scene_id_set = set(scene_ids)
        adjacent = set(zip(scene_ids, scene_ids[1:]))

        state["mediaOrder"] = list(scene_ids)
        state["transitions"] = [
            dict(item)
            for item in state.get("transitions", [])
            if (
                str(item.get("from_id", "")).strip(),
                str(item.get("to_id", "")).strip(),
            )
            in adjacent
        ]

        source_id = target_id = None
        if clone_scene_edit is not None:
            source_id, target_id = clone_scene_edit

        edits: list[dict] = []
        target_already_present = False
        for item in state.get("sceneEdits", []):
            scene_id = str(item.get("scene_id", "")).strip()
            if scene_id not in scene_id_set:
                continue
            copied = dict(item)
            edits.append(copied)
            if target_id is not None and scene_id == target_id:
                target_already_present = True
            if (
                source_id is not None
                and target_id is not None
                and scene_id == source_id
                and target_id in scene_id_set
                and not target_already_present
            ):
                cloned = dict(copied)
                cloned["scene_id"] = target_id
                edits.append(cloned)
                target_already_present = True
        state["sceneEdits"] = edits
        self.store.save_timeline(self.project_id, state)

    def _prepare_scene_mutation(self) -> dict | None:
        try:
            return self._scene_mutation_timeline_state()
        except ValueError as exc:
            self.status_message.emit(f"Scene change blocked · {exc}")
            return None

    def _add_scene(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before adding scenes")
            return
        timeline_state = self._prepare_scene_mutation()
        if timeline_state is None:
            return
        scene_id = self.store.add_scene(self.project_id, "New scene")
        self._reconcile_scene_mutation_timeline(timeline_state)
        self._refresh_scenes(selected_id=scene_id, fallback_row=self.scenes.count())
        self.status_message.emit("Scene added")

    def _duplicate_selected_scene(self) -> None:
        if not self.project_id:
            return
        scene_id = self._selected_scene_id()
        scene = self._scene_by_id(scene_id)
        if scene is None or not scene_id:
            return
        timeline_state = self._prepare_scene_mutation()
        if timeline_state is None:
            return
        render_settings = self.store.get_scene_render_settings(scene_id)
        duplicate_id = self.store.add_scene(
            self.project_id,
            f"{scene['text']} copy",
            position=int(scene["position"]) + 1,
            image_prompt=scene.get("image_prompt", ""),
            voice_text=scene.get("voice_text", ""),
            metadata=scene.get("metadata", {}),
        )
        copied_settings = {
            key: value
            for key, value in render_settings.items()
            if key not in {"reveal_duration", "hold_duration", "extras"}
        }
        copied_settings.update(dict(render_settings.get("extras") or {}))
        self.store.update_scene_render_settings(
            duplicate_id,
            reveal_duration=render_settings["reveal_duration"],
            hold_duration=render_settings["hold_duration"],
            settings=copied_settings,
        )
        object_id_map: dict[str, str] = {}
        for obj in self.store.list_visual_objects(scene_id):
            copied_object_id = self.store.add_visual_object(
                duplicate_id,
                obj["kind"],
                name=obj.get("name", ""),
                source=obj.get("source", ""),
                x=obj.get("x", 0),
                y=obj.get("y", 0),
                width=obj.get("width", 320),
                height=obj.get("height", 180),
                rotation=obj.get("rotation", 0),
                opacity=obj.get("opacity", 1),
                visible=obj.get("visible", True),
                locked=obj.get("locked", False),
                payload=obj.get("payload", {}),
            )
            object_id_map[str(obj["id"])] = copied_object_id

        custom_timing = render_settings.get("custom_object_timing_config") or []
        if isinstance(custom_timing, list) and custom_timing:
            remapped_timing = []
            for raw in custom_timing:
                if not isinstance(raw, dict):
                    remapped_timing.append(raw)
                    continue
                copied = dict(raw)
                old_object_id = str(
                    copied.get("object_id") or copied.get("id") or ""
                ).strip()
                new_object_id = object_id_map.get(old_object_id)
                if new_object_id:
                    copied["object_id"] = new_object_id
                    if "id" in copied:
                        copied["id"] = new_object_id
                remapped_timing.append(copied)
            self.store.update_scene_render_settings(
                duplicate_id,
                settings={"custom_object_timing_config": remapped_timing},
            )
        self._reconcile_scene_mutation_timeline(
            timeline_state,
            clone_scene_edit=(scene_id, duplicate_id),
        )
        self._refresh_scenes(selected_id=duplicate_id)
        self.status_message.emit("Scene duplicated")

    def _move_selected_scene(self, delta: int) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id:
            return
        current_row = self.scenes.currentRow()
        target_row = current_row + int(delta)
        if target_row < 0 or target_row >= self.scenes.count():
            return
        timeline_state = self._prepare_scene_mutation()
        if timeline_state is None:
            return
        self.store.move_scene(scene_id, target_row)
        self._reconcile_scene_mutation_timeline(timeline_state)
        self._refresh_scenes(selected_id=scene_id)
        self.status_message.emit("Scene order updated")

    def _delete_selected_scene(self) -> None:
        if not self.project_id:
            return
        scene_id = self._selected_scene_id()
        if not scene_id:
            return
        timeline_state = self._prepare_scene_mutation()
        if timeline_state is None:
            return
        current_row = self.scenes.currentRow()
        self.store.delete_scene(scene_id)
        rows = self.store.list_scenes(self.project_id)
        if not rows:
            replacement_id = self.store.add_scene(self.project_id, "Blank scene")
            self._reconcile_scene_mutation_timeline(timeline_state)
            self._refresh_scenes(selected_id=replacement_id)
        else:
            self._reconcile_scene_mutation_timeline(timeline_state)
            self._refresh_scenes(fallback_row=min(current_row, len(rows) - 1))
        self.status_message.emit("Scene deleted")

    def _reset_selected_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene before resetting")
            return
        self.draw_button.setChecked(False)
        self.store.reset_scene_render_settings(scene_id)
        self._load_render_controls(scene_id)
        self._refresh_canvas_objects(selected_object_id=self._selected_object_id())
        self.status_message.emit("Scene render settings reset to defaults")

    def _current_render_control_settings(self) -> dict:
        return {
            "style": self.render_style_combo.currentData(),
            "visual_mode": self.visual_mode_combo.currentData(),
            "brush_mode": self.brush_mode_combo.currentData(),
            "hand_style": self.hand_style_combo.currentData(),
            "remove_background_enabled": self.remove_background_check.isChecked(),
            "auto_object_fx_enabled": self.auto_object_fx_check.isChecked(),
            "object_timing_mode": self.object_timing_combo.currentData(),
            "outro_enabled": self.outro_enabled_check.isChecked(),
            "outro_direction": self.outro_direction_combo.currentData(),
            "outro_duration": self.outro_duration_spin.value(),
        }

    def _apply_render_settings_to_all_scenes(self) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id:
            self.status_message.emit(
                "Select a scene before applying drawing settings to all scenes"
            )
            return

        # Persist the currently visible controls first so Apply-to-all operates
        # on what the user sees, not on a stale saved snapshot.
        self.store.update_scene_render_settings(
            scene_id,
            reveal_duration=self.reveal_spin.value(),
            hold_duration=self.hold_spin.value(),
            settings=self._current_render_control_settings(),
        )
        updated = self.store.apply_scene_render_settings_to_project(scene_id)
        self._load_render_controls(scene_id)
        self.status_message.emit(
            f"Drawing settings applied to {updated} scene(s) · object-specific state preserved"
        )

    def _save_selected_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            return
        text = self.scene_text_edit.toPlainText().strip()
        if not text:
            self.status_message.emit("Scene text cannot be empty")
            return
        self.store.update_scene(scene_id, text=text, voice_text=text)
        self.store.update_scene_render_settings(
            scene_id,
            reveal_duration=self.reveal_spin.value(),
            hold_duration=self.hold_spin.value(),
            settings=self._current_render_control_settings(),
        )
        current_row = self.scenes.currentRow()
        self._refresh_scenes(selected_id=scene_id, fallback_row=current_row)
        self.status_message.emit("Scene saved")

    def _persist_freehand_drawing(self, points: list) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            return
        normalized = [[float(point[0]), float(point[1])] for point in points]
        if len(normalized) < 2:
            return
        object_id = self.store.add_visual_object(
            scene_id,
            "drawing",
            name=f"Drawing {len(self.store.list_visual_objects(scene_id)) + 1}",
            x=0.0,
            y=0.0,
            width=CanvasEditor.CANVAS_WIDTH,
            height=CanvasEditor.CANVAS_HEIGHT,
            payload={"points": normalized, "color": "#20232A", "stroke": 5.0},
        )
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Drawing layer saved")

    def _add_text_object(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene before adding an object")
            return
        object_id = self.store.add_visual_object(
            scene_id,
            "text",
            name=f"Text {len(self.store.list_visual_objects(scene_id)) + 1}",
            x=160,
            y=120,
            width=600,
            height=110,
            payload={"text": "Text", "font_size": 42, "color": "#20232A"},
        )
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Text layer added")

    def _add_shape_object(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            self.status_message.emit("Select a scene before adding an object")
            return
        object_id = self.store.add_visual_object(
            scene_id,
            "shape",
            name=f"Shape {len(self.store.list_visual_objects(scene_id)) + 1}",
            x=240,
            y=180,
            width=420,
            height=240,
            payload={"shape": "rect", "fill": "#DDD9CD"},
        )
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Shape layer added")

    def _move_selected_object(self, delta: int) -> None:
        object_id = self._selected_object_id()
        if not object_id:
            return
        current_row = self.layers.currentRow()
        target = current_row + int(delta)
        if target < 0 or target >= self.layers.count():
            return
        self.store.move_visual_object(object_id, target)
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Layer order updated")

    def _delete_selected_object(self) -> None:
        object_id = self._selected_object_id()
        if not object_id:
            return
        self.store.delete_visual_object(object_id)
        self._refresh_canvas_objects()
        self.status_message.emit("Layer deleted")

    def _canvas_object_transform_changed(
        self,
        object_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
        rotation: float,
    ) -> None:
        self.store.update_visual_object(
            object_id,
            x=x,
            y=y,
            width=width,
            height=height,
            rotation=rotation,
        )
        self.status_message.emit("Object transform saved")

    def _refresh_media(self) -> None:
        self.media_list.clear()
        if not self.project_id:
            self.media_list.addItem("No project")
            return
        media = self.store.list_media(self.project_id)
        if not media:
            self.media_list.addItem("Drop in image, video or audio")
            return
        for index, item in enumerate(media):
            icon = "IMG" if item["kind"] == "image" else ("VID" if item["kind"] == "video" else "AUD")
            self.media_list.addItem(f"{icon}   {item['original_name']}")
            self.media_list.item(index).setData(Qt.ItemDataRole.UserRole, item["id"])

    def _add_media_to_canvas(self, list_item) -> None:
        scene_id = self._selected_scene_id()
        if not self.project_id or not scene_id or list_item is None:
            return
        media_id = str(list_item.data(Qt.ItemDataRole.UserRole) or "")
        if not media_id:
            return
        media = next((row for row in self.store.list_media(self.project_id) if row["id"] == media_id), None)
        if media is None or media["kind"] not in {"image", "video"}:
            return
        object_id = self.store.add_visual_object(
            scene_id,
            media["kind"],
            name=media["original_name"],
            source=media["file_path"],
            x=160,
            y=90,
            width=640,
            height=360,
            payload={"media_id": media_id, "fit": "contain"},
        )
        self._refresh_canvas_objects(selected_object_id=object_id)
        self.status_message.emit("Media added to canvas")

    def _import_media(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before importing media")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import media",
            "",
            "Media (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.webm *.mp3 *.wav *.m4a *.flac *.ogg);;All files (*)",
        )
        if not paths:
            return
        media_root = Path(self.store.db_path).parent / "media" / self.project_id
        media_root.mkdir(parents=True, exist_ok=True)
        image_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        video_ext = {".mp4", ".mov", ".mkv", ".webm"}
        audio_ext = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}
        imported = 0
        for source_raw in paths:
            source = Path(source_raw)
            ext = source.suffix.lower()
            if ext not in image_ext | video_ext | audio_ext:
                continue
            kind = "image" if ext in image_ext else ("video" if ext in video_ext else "audio")
            target = media_root / f"{uuid.uuid4().hex[:8]}-{source.name}"
            shutil.copy2(source, target)
            self.store.add_media(self.project_id, kind, source.name, str(target))
            imported += 1
        self._refresh_media()
        self.status_message.emit(f"Imported {imported} media file(s)")

    def _export_media(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before exporting")
            return
        media = [item for item in self.store.list_media(self.project_id) if item["kind"] in {"image", "video"}]
        if not media:
            self.status_message.emit("Import at least one image or video before exporting")
            return
        output, _ = QFileDialog.getSaveFileName(self, "Export video", "NolaneStudio-export.mp4", "MP4 video (*.mp4)")
        if not output:
            return
        if not output.lower().endswith(".mp4"):
            output += ".mp4"
        clips = [ExportClip(item["file_path"], item["kind"], 6.0) for item in media]
        self.export_button.setEnabled(False)
        self.export_button.setText("Exporting…")
        self.status_message.emit("Export started · media is normalized sequentially to keep RAM low")
        self._export_worker = ExportWorker(clips, output, self)
        self._export_worker.completed.connect(self._export_complete)
        self._export_worker.failed.connect(self._export_failed)
        self._export_worker.start()

    def _export_complete(self, output: str) -> None:
        self.export_button.setEnabled(True)
        self.export_button.setText("Export video")
        self.status_message.emit(f"Export complete · {output}")
        self._export_worker = None

    def _export_failed(self, message: str) -> None:
        self.export_button.setEnabled(True)
        self.export_button.setText("Export video")
        self.status_message.emit(f"Export failed · {message}")
        self._export_worker = None


class LibraryPage(QWidget):
    open_project = Signal(str, str)

    def __init__(self, store: ProjectStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        outer = QVBoxLayout(self)
        outer.setContentsMargins(38, 28, 38, 28)
        outer.setSpacing(20)
        head = QHBoxLayout()
        head.addWidget(_heading("Local library", "Projects that stay yours", "No expiry timer. No account gate. No cloud required."))
        head.addStretch(1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh)
        outer.addLayout(head)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.grid_host)
        outer.addWidget(scroll, 1)
        self.refresh()

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        projects = self.store.list_projects(limit=24)
        if not projects:
            empty = Surface(accent=True)
            layout = QVBoxLayout(empty)
            layout.setContentsMargins(28, 24, 28, 24)
            layout.addWidget(SectionTitle("Ready when you are", "Nothing here yet", "Create a project and it will appear here automatically."))
            self.grid.addWidget(empty, 0, 0, 1, 2)
            return
        for idx, project in enumerate(projects):
            card = Surface(raised=True)
            card.setMinimumHeight(150)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 16, 18, 16)
            title = QLabel(project.get("title") or "Untitled project")
            title.setObjectName("sectionTitle")
            meta = QLabel(f"{project.get('output_w', 1280)} × {project.get('output_h', 720)}   ·   {project.get('expected_image_count', 0)} scenes")
            meta.setObjectName("muted")
            layout.addWidget(title)
            layout.addWidget(meta)
            layout.addStretch(1)
            open_button = QPushButton("Open in Studio")
            open_button.clicked.connect(lambda _=False, p=project: self.open_project.emit(p["project_id"], p.get("title") or "Untitled project"))
            layout.addWidget(open_button)
            self.grid.addWidget(card, idx // 2, idx % 2)


class ProvidersPage(QWidget):
    status_message = Signal(str)

    def __init__(
        self,
        provider_descriptors: Callable[[], list],
        settings_store: SettingsStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.provider_descriptors = provider_descriptors
        self.settings_store = settings_store
        current = settings_store.load()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(38, 28, 38, 28)
        outer.setSpacing(20)
        outer.addWidget(_heading("Provider layer", "Bring the model you want", "Analysis, image, vision, speech and voice are capabilities, not hard-coded vendors."))

        safe = Surface(accent=True)
        safe_layout = QHBoxLayout(safe)
        safe_layout.setContentsMargins(20, 18, 20, 18)
        safe_layout.addWidget(Dot("#4ED7C5", 10))
        safe_text = QVBoxLayout()
        safe_text.addWidget(QLabel("8 GB-safe by default"))
        sub = QLabel("No local LLM, speech model or image model is loaded just by opening the app.")
        sub.setObjectName("muted")
        safe_text.addWidget(sub)
        safe_layout.addLayout(safe_text)
        safe_layout.addStretch(1)
        outer.addWidget(safe)

        config = Surface()
        cfg = QGridLayout(config)
        cfg.setContentsMargins(20, 18, 20, 18)
        cfg.setHorizontalSpacing(16)
        cfg.setVerticalSpacing(12)
        cfg.addWidget(
            SectionTitle("API", "Connection settings", "Environment variables remain supported for automation."),
            0,
            0,
            1,
            2,
        )
        rows = [
            ("Analysis endpoint", "ai_endpoint", current.analysis_base_url, "https://provider.example/v1"),
            ("Analysis model", "ai_model", current.analysis_model, "text-analysis-model"),
            ("Image endpoint", "image_endpoint", current.image_base_url, "https://provider.example/v1"),
            ("Image model", "image_model", current.image_model, "image-model"),
            ("Vision endpoint", "vision_endpoint", current.vision_base_url, "https://provider.example/v1"),
            ("Vision model", "vision_model", current.vision_model, "vision-model"),
            ("STT endpoint", "stt_endpoint", current.stt_base_url, "https://provider.example/v1"),
            ("STT model", "stt_model", current.stt_model, "transcription-model"),
            ("TTS endpoint", "tts_endpoint", current.tts_base_url, "https://provider.example/v1"),
            ("TTS model", "tts_model", current.tts_model, "speech-model"),
            ("Advanced TTS endpoint", "tts_advanced_endpoint", current.tts_advanced_endpoint, "https://provider.example/tts"),
            ("Voice catalog endpoint", "tts_voices_endpoint", current.tts_voices_endpoint, "https://provider.example/voices"),
        ]
        for row, (label, attr, value, placeholder) in enumerate(rows, start=1):
            cfg.addWidget(QLabel(label), row, 0)
            edit = QLineEdit(value)
            edit.setPlaceholderText(placeholder)
            setattr(self, attr, edit)
            cfg.addWidget(edit, row, 1)
        save = QPushButton("Save locally")
        save.setObjectName("primary")
        save.clicked.connect(self._save_settings)
        cfg.addWidget(save, len(rows) + 1, 1, alignment=Qt.AlignmentFlag.AlignRight)
        outer.addWidget(config)

        status = Surface()
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(20, 18, 20, 18)
        status_layout.addWidget(SectionTitle("Runtime", "Detected providers"))
        descriptors = self.provider_descriptors()
        if descriptors:
            for descriptor in descriptors:
                row = QHBoxLayout()
                row.addWidget(Dot("#54D49A"))
                row.addWidget(QLabel(descriptor.name))
                row.addStretch(1)
                caps = [name for name in ("analysis", "image", "vision", "stt", "tts", "clone", "design", "list_voices") if getattr(descriptor.capabilities, name)]
                chip = QLabel(" · ".join(caps) or "registered")
                chip.setObjectName("chip")
                row.addWidget(chip)
                status_layout.addLayout(row)
        else:
            empty = QLabel("No provider configured yet. The editor remains fully usable offline.")
            empty.setObjectName("muted")
            status_layout.addWidget(empty)
        outer.addWidget(status)
        outer.addStretch(1)

    def _save_settings(self) -> None:
        settings = ProviderSettings(
            analysis_base_url=self.ai_endpoint.text().strip(),
            analysis_model=self.ai_model.text().strip(),
            image_base_url=self.image_endpoint.text().strip(),
            image_model=self.image_model.text().strip(),
            vision_base_url=self.vision_endpoint.text().strip(),
            vision_model=self.vision_model.text().strip(),
            stt_base_url=self.stt_endpoint.text().strip(),
            stt_model=self.stt_model.text().strip(),
            tts_base_url=self.tts_endpoint.text().strip(),
            tts_model=self.tts_model.text().strip(),
            tts_advanced_endpoint=self.tts_advanced_endpoint.text().strip(),
            tts_voices_endpoint=self.tts_voices_endpoint.text().strip(),
        )
        self.settings_store.save(settings)
        self.status_message.emit("Provider settings saved locally · restart to rebuild the provider registry")
