from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_reset_scene_button_restores_render_controls_without_deleting_layer(tmp_path: Path):
    app = _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Reset UI")
    store.replace_scenes("p1", [Scene(0, "Narration stays")])
    scene = store.list_scenes("p1")[0]
    scene_id = scene["id"]
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Layer stays",
        payload={"fill": "#3366FF"},
    )
    store.update_scene_render_settings(
        scene_id,
        reveal_duration=2.0,
        hold_duration=3.0,
        settings={
            "style": "color_reveal",
            "visual_mode": "camera_motion",
            "brush_mode": "rl",
            "hand_style": "hand-3.png",
            "remove_background_enabled": True,
            "auto_object_fx_enabled": True,
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"id": object_id, "pause": 0.1, "draw": 0.8, "push": 0.2}
            ],
        },
    )

    page = StudioPage(store)
    statuses: list[str] = []
    page.status_message.connect(statuses.append)
    page.load_project("p1", "Reset UI", [])
    app.processEvents()

    assert page.reset_scene_button.isEnabled()
    assert "without deleting" in page.reset_scene_button.toolTip().lower()
    assert page.render_style_combo.currentData() == "color_reveal"
    assert page.object_timing_combo.currentData() == "custom"
    assert page.layers.count() == 1

    page.reset_scene_button.click()
    app.processEvents()

    assert page.render_style_combo.currentData() == "whiteboard"
    assert page.visual_mode_combo.currentData() == "drawing"
    assert page.brush_mode_combo.currentData() == "lr"
    assert page.hand_style_combo.currentData() == "hand-1.png"
    assert page.reveal_spin.value() == 8.0
    assert page.hold_spin.value() == 1.0
    assert page.remove_background_check.isChecked() is False
    assert page.auto_object_fx_check.isChecked() is False
    assert page.object_timing_combo.currentData() == "fixed"
    assert page.layers.count() == 1
    assert store.list_visual_objects(scene_id)[0]["id"] == object_id
    assert store.list_scenes("p1")[0]["text"] == "Narration stays"
    assert statuses[-1] == "Scene render settings reset to defaults"
