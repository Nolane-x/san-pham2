from __future__ import annotations

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def _scene(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening")])
    return store, store.list_scenes("p1")[0]["id"]


def test_scene_render_settings_round_trip_recovered_drawing_contract(tmp_path):
    store, scene_id = _scene(tmp_path)

    store.update_scene_render_settings(
        scene_id,
        reveal_duration=6.5,
        hold_duration=1.75,
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

    scene = store.list_scenes("p1")[0]
    settings = store.get_scene_render_settings(scene_id)
    assert scene["reveal_duration"] == 6.5
    assert scene["hold_duration"] == 1.75
    assert settings["style"] == "color_reveal"
    assert settings["visual_mode"] == "drawing"
    assert settings["brush_mode"] == "rl"
    assert settings["hand_style"] == "hand-2.png"
    assert settings["remove_background_enabled"] is True
    assert settings["auto_object_fx_enabled"] is True
    assert settings["object_timing_mode"] == "custom"
    assert settings["reveal_duration"] == 6.5
    assert settings["hold_duration"] == 1.75


def test_scene_render_settings_are_normalized_fail_safe(tmp_path):
    store, scene_id = _scene(tmp_path)

    store.update_scene_render_settings(
        scene_id,
        reveal_duration=-50,
        hold_duration=-10,
        settings={"style": "not-a-style", "visual_mode": "not-a-mode"},
    )

    settings = store.get_scene_render_settings(scene_id)
    assert settings["style"] == "whiteboard"
    assert settings["visual_mode"] == "drawing"
    assert settings["reveal_duration"] == 0.0
    assert settings["hold_duration"] == 0.0
