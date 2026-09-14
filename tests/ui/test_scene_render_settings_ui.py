from __future__ import annotations

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _page(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening"), Scene(1, "Closing")])
    scene_id = store.list_scenes("p1")[0]["id"]
    store.update_scene_render_settings(
        scene_id,
        reveal_duration=5.25,
        hold_duration=1.5,
        settings={
            "style": "color_reveal",
            "visual_mode": "drawing",
            "brush_mode": "rl",
            "hand_style": "hand-2.png",
            "remove_background_enabled": True,
            "auto_object_fx_enabled": True,
            "object_timing_mode": "custom",
        },
    )
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])
    page.scenes.setCurrentRow(0)
    return store, page, scene_id


def test_inspector_loads_recovered_drawing_and_timing_settings(tmp_path):
    _store, page, _scene_id = _page(tmp_path)

    assert page.reveal_spin.value() == 5.25
    assert page.hold_spin.value() == 1.5
    assert page.render_style_combo.currentData() == "color_reveal"
    assert page.visual_mode_combo.currentData() == "drawing"
    assert page.brush_mode_combo.currentData() == "rl"
    assert page.hand_style_combo.currentData() == "hand-2.png"
    assert page.remove_background_check.isChecked() is True
    assert page.auto_object_fx_check.isChecked() is True
    assert page.object_timing_combo.currentData() == "custom"


def test_save_scene_persists_recovered_drawing_and_timing_settings(tmp_path):
    store, page, scene_id = _page(tmp_path)

    page.reveal_spin.setValue(7.75)
    page.hold_spin.setValue(2.25)
    page.render_style_combo.setCurrentIndex(page.render_style_combo.findData("whiteboard"))
    page.visual_mode_combo.setCurrentIndex(page.visual_mode_combo.findData("camera_motion"))
    page.brush_mode_combo.setCurrentIndex(page.brush_mode_combo.findData("lr"))
    page.hand_style_combo.setCurrentIndex(page.hand_style_combo.findData("hand-3.png"))
    page.remove_background_check.setChecked(False)
    page.auto_object_fx_check.setChecked(False)
    page.object_timing_combo.setCurrentIndex(page.object_timing_combo.findData("fixed"))
    page._save_selected_scene()

    settings = store.get_scene_render_settings(scene_id)
    assert settings["reveal_duration"] == 7.75
    assert settings["hold_duration"] == 2.25
    assert settings["style"] == "whiteboard"
    assert settings["visual_mode"] == "camera_motion"
    assert settings["brush_mode"] == "lr"
    assert settings["hand_style"] == "hand-3.png"
    assert settings["remove_background_enabled"] is False
    assert settings["auto_object_fx_enabled"] is False
    assert settings["object_timing_mode"] == "fixed"


def test_duplicate_scene_preserves_render_settings_and_objects(tmp_path):
    store, page, scene_id = _page(tmp_path)
    original_object = store.add_visual_object(
        scene_id,
        "shape",
        name="Object",
        x=33,
        y=44,
        width=555,
        height=222,
        rotation=9,
        payload={"fill": "#abcdef"},
    )
    page._refresh_canvas_objects(selected_object_id=original_object)

    page._duplicate_selected_scene()

    scenes = store.list_scenes("p1")
    assert len(scenes) == 3
    duplicate = scenes[1]
    settings = store.get_scene_render_settings(duplicate["id"])
    assert settings["reveal_duration"] == 5.25
    assert settings["hold_duration"] == 1.5
    assert settings["style"] == "color_reveal"
    assert settings["brush_mode"] == "rl"
    assert settings["remove_background_enabled"] is True
    assert settings["auto_object_fx_enabled"] is True
    assert settings["object_timing_mode"] == "custom"

    copied = store.list_visual_objects(duplicate["id"])
    assert len(copied) == 1
    assert copied[0]["name"] == "Object"
    assert copied[0]["x"] == 33
    assert copied[0]["rotation"] == 9
    assert copied[0]["payload"]["fill"] == "#abcdef"
