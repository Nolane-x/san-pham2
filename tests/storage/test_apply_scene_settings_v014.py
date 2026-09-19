from __future__ import annotations

from pathlib import Path

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def test_apply_scene_render_settings_to_project_preserves_object_specific_state(
    tmp_path: Path,
):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Apply settings")
    store.replace_scenes(
        "p1",
        [
            Scene(0, "Source"),
            Scene(1, "Target one"),
            Scene(2, "Target two"),
        ],
    )
    source, target_one, target_two = store.list_scenes("p1")

    target_object = store.add_visual_object(
        target_one["id"],
        "shape",
        name="Target object",
        payload={"fill": "#3366FF"},
    )
    store.update_scene(
        target_one["id"],
        metadata={"voice_path": "target-one.wav", "marker": "keep-target-one"},
    )
    store.update_scene_render_settings(
        target_one["id"],
        reveal_duration=1.5,
        hold_duration=2.5,
        settings={
            "style": "whiteboard",
            "visual_mode": "drawing",
            "brush_mode": "lr",
            "hand_style": "hand-1.png",
            "remove_background_enabled": False,
            "auto_object_fx_enabled": False,
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {
                    "object_id": target_object,
                    "pause": 0.2,
                    "draw": 0.7,
                    "push": 0.1,
                }
            ],
            "custom_object_sound_config": [{"object_id": target_object, "slot": "local"}],
            "custom_draw_points": [[1, 2], [3, 4]],
            "target_only_extra": {"keep": True},
        },
    )
    store.update_scene(
        target_two["id"],
        metadata={"generated_image_media_id": "target-two-image"},
    )
    store.update_scene_render_settings(
        target_two["id"],
        reveal_duration=3.0,
        hold_duration=4.0,
        settings={
            "object_timing_mode": "fixed",
            "custom_camera_config": [{"phase": "target-only"}],
            "target_two_extra": 42,
        },
    )

    store.update_scene_render_settings(
        source["id"],
        reveal_duration=9.25,
        hold_duration=1.75,
        settings={
            "style": "color_reveal",
            "visual_mode": "camera_motion",
            "brush_mode": "rl",
            "hand_style": "hand-3.png",
            "remove_background_enabled": True,
            "auto_object_fx_enabled": True,
            "object_timing_mode": "fixed",
            "custom_draw_points": [["source-only"]],
            "source_only_extra": "do-not-copy",
        },
    )

    updated = store.apply_scene_render_settings_to_project(source["id"])

    assert updated == 3
    for scene in (source, target_one, target_two):
        settings = store.get_scene_render_settings(scene["id"])
        assert settings["reveal_duration"] == 9.25
        assert settings["hold_duration"] == 1.75
        assert settings["style"] == "color_reveal"
        assert settings["visual_mode"] == "camera_motion"
        assert settings["brush_mode"] == "rl"
        assert settings["hand_style"] == "hand-3.png"
        assert settings["remove_background_enabled"] is True
        assert settings["auto_object_fx_enabled"] is True

    target_one_settings = store.get_scene_render_settings(target_one["id"])
    assert target_one_settings["object_timing_mode"] == "custom"
    assert target_one_settings["custom_object_timing_config"] == [
        {
            "object_id": target_object,
            "pause": 0.2,
            "draw": 0.7,
            "push": 0.1,
        }
    ]
    assert target_one_settings["custom_object_sound_config"] == [
        {"object_id": target_object, "slot": "local"}
    ]
    assert target_one_settings["custom_draw_points"] == [[1, 2], [3, 4]]
    assert target_one_settings["extras"]["target_only_extra"] == {"keep": True}
    assert "source_only_extra" not in target_one_settings["extras"]

    target_two_settings = store.get_scene_render_settings(target_two["id"])
    assert target_two_settings["custom_camera_config"] == [{"phase": "target-only"}]
    assert target_two_settings["extras"]["target_two_extra"] == 42
    assert "source_only_extra" not in target_two_settings["extras"]

    reloaded = {row["id"]: row for row in store.list_scenes("p1")}
    assert reloaded[target_one["id"]]["metadata"]["voice_path"] == "target-one.wav"
    assert reloaded[target_one["id"]]["metadata"]["marker"] == "keep-target-one"
    assert (
        reloaded[target_two["id"]]["metadata"]["generated_image_media_id"]
        == "target-two-image"
    )
