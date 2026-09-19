from __future__ import annotations

from pathlib import Path

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def test_reset_scene_render_settings_preserves_content_and_non_render_metadata(tmp_path: Path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Reset")
    store.replace_scenes("p1", [Scene(0, "Keep this scene text")])
    scene = store.list_scenes("p1")[0]
    scene_id = scene["id"]

    store.update_scene(
        scene_id,
        metadata={
            "voice_path": "voice.wav",
            "voice_media_id": f"voice-{scene_id}",
            "ai_analysis": {"labels": [{"label": "Keep me"}]},
            "generated_image_media_id": f"generated-image-{scene_id}",
        },
    )
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Persistent layer",
        payload={"fill": "#3366FF"},
    )
    store.update_scene_render_settings(
        scene_id,
        reveal_duration=2.5,
        hold_duration=4.0,
        settings={
            "style": "color_reveal",
            "visual_mode": "camera_motion",
            "brush_mode": "rl",
            "hand_style": "hand-3.png",
            "remove_background_enabled": True,
            "auto_object_fx_enabled": True,
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"id": object_id, "pause": 0.2, "draw": 0.6, "push": 0.1}
            ],
            "custom_draw_points": [[0, 0], [1, 1]],
            "future_recovered_setting": {"must": "be cleared with render state"},
        },
    )

    defaults = store.reset_scene_render_settings(scene_id)

    assert defaults["style"] == "whiteboard"
    assert defaults["visual_mode"] == "drawing"
    assert defaults["reveal_duration"] == 8.0
    assert defaults["hold_duration"] == 1.0
    assert defaults["brush_mode"] == "lr"
    assert defaults["hand_style"] == "hand-1.png"
    assert defaults["remove_background_enabled"] is False
    assert defaults["auto_object_fx_enabled"] is False
    assert defaults["object_timing_mode"] == "fixed"
    assert defaults["custom_object_timing_config"] == []
    assert defaults["custom_draw_points"] == []
    assert defaults["extras"] == {}

    stored = store.get_scene_render_settings(scene_id)
    assert stored == defaults

    reloaded = store.list_scenes("p1")[0]
    assert reloaded["text"] == "Keep this scene text"
    assert "render_config" not in reloaded["metadata"]
    assert reloaded["metadata"]["voice_path"] == "voice.wav"
    assert reloaded["metadata"]["voice_media_id"] == f"voice-{scene_id}"
    assert reloaded["metadata"]["ai_analysis"]["labels"][0]["label"] == "Keep me"
    assert reloaded["metadata"]["generated_image_media_id"] == f"generated-image-{scene_id}"

    objects = store.list_visual_objects(scene_id)
    assert [item["id"] for item in objects] == [object_id]
    assert objects[0]["name"] == "Persistent layer"
