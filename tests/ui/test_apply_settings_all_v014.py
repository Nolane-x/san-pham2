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


def test_apply_drawing_settings_to_all_uses_visible_controls_and_keeps_target_timing(
    tmp_path: Path,
):
    app = _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Apply settings UI")
    store.replace_scenes("p1", [Scene(0, "Source"), Scene(1, "Target")])
    source, target = store.list_scenes("p1")
    target_object = store.add_visual_object(
        target["id"],
        "shape",
        name="Target layer",
        payload={"fill": "#3366FF"},
    )
    store.update_scene_render_settings(
        target["id"],
        settings={
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {
                    "object_id": target_object,
                    "pause": 0.3,
                    "draw": 0.8,
                    "push": 0.2,
                }
            ],
        },
    )

    page = StudioPage(store)
    statuses: list[str] = []
    page.status_message.connect(statuses.append)
    page.load_project("p1", "Apply settings UI", [])
    app.processEvents()

    assert page._selected_scene_id() == source["id"]
    assert page.apply_render_settings_all_button.isEnabled()
    assert "object-specific" in page.apply_render_settings_all_button.toolTip().lower()

    page.reveal_spin.setValue(6.5)
    page.hold_spin.setValue(2.25)
    page.render_style_combo.setCurrentIndex(
        page.render_style_combo.findData("color_reveal")
    )
    page.visual_mode_combo.setCurrentIndex(
        page.visual_mode_combo.findData("camera_motion")
    )
    page.brush_mode_combo.setCurrentIndex(page.brush_mode_combo.findData("rl"))
    page.hand_style_combo.setCurrentIndex(
        page.hand_style_combo.findData("hand-1.png")
    )
    page.remove_background_check.setChecked(True)
    page.auto_object_fx_check.setChecked(True)

    page.apply_render_settings_all_button.click()
    app.processEvents()

    source_settings = store.get_scene_render_settings(source["id"])
    target_settings = store.get_scene_render_settings(target["id"])
    for settings in (source_settings, target_settings):
        assert settings["reveal_duration"] == 6.5
        assert settings["hold_duration"] == 2.25
        assert settings["style"] == "color_reveal"
        assert settings["visual_mode"] == "camera_motion"
        assert settings["brush_mode"] == "rl"
        assert settings["hand_style"] == "hand-1.png"
        assert settings["remove_background_enabled"] is True
        assert settings["auto_object_fx_enabled"] is True

    assert target_settings["object_timing_mode"] == "custom"
    assert target_settings["custom_object_timing_config"] == [
        {
            "object_id": target_object,
            "pause": 0.3,
            "draw": 0.8,
            "push": 0.2,
        }
    ]
    assert statuses[-1] == (
        "Drawing settings applied to 2 scene(s) · object-specific state preserved"
    )
