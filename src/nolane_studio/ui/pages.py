from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from .widgets import CanvasPreview, Dot, SectionTitle, Surface


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
        except Exception as exc:  # boundary: surface media/runtime errors in the UI
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
        tb.setContentsMargins(20, 10, 20, 10)
        tb.setSpacing(8)
        self.project_label = QLabel("No project open")
        self.project_label.setObjectName("sectionTitle")
        tb.addWidget(self.project_label)
        status = QLabel("LOCAL-FIRST")
        status.setObjectName("chip")
        tb.addWidget(status)
        tb.addStretch(1)
        preview = QPushButton("Preview")
        preview.setToolTip("Preview uses the current scene canvas")
        self.export_button = QPushButton("Export video")
        self.export_button.setObjectName("primary")
        self.export_button.clicked.connect(self._export_media)
        tb.addWidget(preview)
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
        media_title = QLabel("Media")
        media_title.setObjectName("sectionTitle")
        media_header.addWidget(media_title)
        media_header.addStretch(1)
        import_media = QPushButton("Import")
        import_media.setObjectName("ghost")
        import_media.clicked.connect(self._import_media)
        media_header.addWidget(import_media)
        scenes_layout.addLayout(media_header)
        self.media_list = QListWidget()
        self.media_list.setMaximumHeight(138)
        scenes_layout.addWidget(self.media_list)

        canvas_shell = QFrame()
        canvas_layout = QVBoxLayout(canvas_shell)
        canvas_layout.setContentsMargins(16, 16, 16, 16)
        canvas_layout.setSpacing(12)
        canvas_head = QHBoxLayout()
        canvas_head.addWidget(SectionTitle("Composition", "Canvas", "16:9 · 1280 × 720 · 24 fps"))
        canvas_head.addStretch(1)
        zoom = QLabel("Fit  •  100%")
        zoom.setObjectName("chip")
        canvas_head.addWidget(zoom)
        canvas_layout.addLayout(canvas_head)
        canvas_surface = Surface(raised=True)
        canvas_surface_layout = QVBoxLayout(canvas_surface)
        canvas_surface_layout.setContentsMargins(8, 8, 8, 8)
        self.canvas = CanvasPreview()
        canvas_surface_layout.addWidget(self.canvas, 1)
        canvas_layout.addWidget(canvas_surface, 1)

        inspector = Surface()
        inspector.setMinimumWidth(250)
        inspector.setMaximumWidth(330)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(16, 14, 16, 14)
        inspector_layout.setSpacing(12)
        inspector_layout.addWidget(SectionTitle("Selected scene", "Inspector"))
        tabs = QComboBox()
        tabs.addItems(["Drawing", "Motion", "Voice", "Timing"])
        inspector_layout.addWidget(tabs)

        scene_text_label = QLabel("Scene text")
        scene_text_label.setObjectName("muted")
        inspector_layout.addWidget(scene_text_label)
        self.scene_text_edit = QTextEdit()
        self.scene_text_edit.setPlaceholderText("Select a scene to edit its narration or description")
        self.scene_text_edit.setMinimumHeight(92)
        inspector_layout.addWidget(self.scene_text_edit)
        save_scene = QPushButton("Save scene")
        save_scene.setObjectName("primary")
        save_scene.clicked.connect(self._save_selected_scene)
        inspector_layout.addWidget(save_scene)

        for label, value in (("Reveal", "8.0 s"), ("Hold", "1.0 s"), ("Brush", "Left → right"), ("Camera", "Static")):
            row = QFrame()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 4, 0, 4)
            k = QLabel(label)
            k.setObjectName("muted")
            v = QLabel(value)
            v.setStyleSheet("font-weight:700;color:#F5F7FB")
            lay.addWidget(k)
            lay.addStretch(1)
            lay.addWidget(v)
            inspector_layout.addWidget(row)
        inspector_layout.addWidget(QCheckBox("Remove image background"))
        inspector_layout.addWidget(QCheckBox("Auto object sound FX"))
        inspector_layout.addStretch(1)
        inspector_layout.addWidget(QPushButton("Reset scene"))

        workspace.addWidget(scenes_panel)
        workspace.addWidget(canvas_shell)
        workspace.addWidget(inspector)
        workspace.setStretchFactor(0, 0)
        workspace.setStretchFactor(1, 1)
        workspace.setStretchFactor(2, 0)
        workspace.setSizes([260, 735, 285])

        timeline = Surface()
        timeline.setMinimumHeight(155)
        timeline_layout = QVBoxLayout(timeline)
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
        vertical.setSizes([600, 180])

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
            self.scene_text_edit.clear()
            self.scene_text_edit.setEnabled(False)
            return
        scene = self._scene_by_id(current.data(Qt.ItemDataRole.UserRole))
        if scene is None:
            self.scene_text_edit.clear()
            self.scene_text_edit.setEnabled(False)
            return
        self.scene_text_edit.setEnabled(True)
        self.scene_text_edit.setPlainText(scene["text"])

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

    def _add_scene(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before adding scenes")
            return
        scene_id = self.store.add_scene(self.project_id, "New scene")
        self._refresh_scenes(selected_id=scene_id, fallback_row=self.scenes.count())
        self.status_message.emit("Scene added")

    def _duplicate_selected_scene(self) -> None:
        if not self.project_id:
            return
        scene_id = self._selected_scene_id()
        scene = self._scene_by_id(scene_id)
        if scene is None:
            return
        duplicate_id = self.store.add_scene(
            self.project_id,
            f"{scene['text']} copy",
            position=int(scene["position"]) + 1,
            image_prompt=scene.get("image_prompt", ""),
            voice_text=scene.get("voice_text", ""),
            metadata=scene.get("metadata", {}),
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
        self.store.move_scene(scene_id, target_row)
        self._refresh_scenes(selected_id=scene_id)
        self.status_message.emit("Scene order updated")

    def _delete_selected_scene(self) -> None:
        if not self.project_id:
            return
        scene_id = self._selected_scene_id()
        if not scene_id:
            return
        current_row = self.scenes.currentRow()
        self.store.delete_scene(scene_id)
        rows = self.store.list_scenes(self.project_id)
        if not rows:
            replacement_id = self.store.add_scene(self.project_id, "Blank scene")
            self._refresh_scenes(selected_id=replacement_id)
        else:
            self._refresh_scenes(fallback_row=min(current_row, len(rows) - 1))
        self.status_message.emit("Scene deleted")

    def _save_selected_scene(self) -> None:
        scene_id = self._selected_scene_id()
        if not scene_id:
            return
        text = self.scene_text_edit.toPlainText().strip()
        if not text:
            self.status_message.emit("Scene text cannot be empty")
            return
        self.store.update_scene(scene_id, text=text, voice_text=text)
        current_row = self.scenes.currentRow()
        self._refresh_scenes(selected_id=scene_id, fallback_row=current_row)
        self.status_message.emit("Scene saved")

    def _refresh_media(self) -> None:
        self.media_list.clear()
        if not self.project_id:
            self.media_list.addItem("No project")
            return
        media = self.store.list_media(self.project_id)
        if not media:
            self.media_list.addItem("Drop in images or video")
            return
        for item in media:
            icon = "IMG" if item["kind"] == "image" else ("VID" if item["kind"] == "video" else "AUD")
            self.media_list.addItem(f"{icon}   {item['original_name']}")

    def _import_media(self) -> None:
        if not self.project_id:
            self.status_message.emit("Create or open a project before importing media")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import media",
            "",
            "Media (*.png *.jpg *.jpeg *.webp *.bmp *.mp4 *.mov *.mkv *.webm);;All files (*)",
        )
        if not paths:
            return
        media_root = Path(self.store.db_path).parent / "media" / self.project_id
        media_root.mkdir(parents=True, exist_ok=True)
        image_ext = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
        video_ext = {".mp4", ".mov", ".mkv", ".webm"}
        imported = 0
        for source_raw in paths:
            source = Path(source_raw)
            ext = source.suffix.lower()
            if ext not in image_ext | video_ext:
                continue
            kind = "image" if ext in image_ext else "video"
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
        outer.addWidget(_heading("Provider layer", "Bring the model you want", "Analysis and voice are capabilities, not hard-coded vendors."))

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
        cfg.addWidget(SectionTitle("API", "Connection settings", "Environment variables remain supported for automation."), 0, 0, 1, 2)
        cfg.addWidget(QLabel("Analysis endpoint"), 1, 0)
        self.ai_endpoint = QLineEdit(current.analysis_base_url)
        self.ai_endpoint.setPlaceholderText("https://provider.example/v1")
        cfg.addWidget(self.ai_endpoint, 1, 1)
        cfg.addWidget(QLabel("Analysis model"), 2, 0)
        self.ai_model = QLineEdit(current.analysis_model)
        self.ai_model.setPlaceholderText("model-name")
        cfg.addWidget(self.ai_model, 2, 1)
        cfg.addWidget(QLabel("TTS endpoint"), 3, 0)
        self.tts_endpoint = QLineEdit(current.tts_base_url)
        self.tts_endpoint.setPlaceholderText("https://provider.example/v1")
        cfg.addWidget(self.tts_endpoint, 3, 1)
        cfg.addWidget(QLabel("TTS model"), 4, 0)
        self.tts_model = QLineEdit(current.tts_model)
        self.tts_model.setPlaceholderText("speech-model")
        cfg.addWidget(self.tts_model, 4, 1)
        save = QPushButton("Save locally")
        save.setObjectName("primary")
        save.clicked.connect(self._save_settings)
        cfg.addWidget(save, 5, 1, alignment=Qt.AlignmentFlag.AlignRight)
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
                caps = [name for name in ("analysis", "tts", "clone", "design") if getattr(descriptor.capabilities, name)]
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
            tts_base_url=self.tts_endpoint.text().strip(),
            tts_model=self.tts_model.text().strip(),
        )
        self.settings_store.save(settings)
        self.status_message.emit("Provider settings saved locally · restart to rebuild the provider registry")
