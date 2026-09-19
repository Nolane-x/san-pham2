from __future__ import annotations

from nolane_studio.domain import Scene
from nolane_studio.render.scene_plan import build_scene_render_plan
from nolane_studio.storage.store import ProjectStore


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Render plan")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    return store


def test_scene_render_plan_follows_persisted_scene_order_and_settings(tmp_path):
    store = _store(tmp_path)
    first, second = store.list_scenes("p1")
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=2.5,
        hold_duration=1.5,
        settings={"style": "color_reveal", "visual_mode": "drawing"},
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=4.0,
        hold_duration=2.0,
        settings={
            "style": "whiteboard",
            "visual_mode": "camera_motion",
            "custom_camera_enabled": True,
            "custom_camera_config": [{"action": "zoom_in_out"}],
        },
    )

    plans = build_scene_render_plan(store, "p1")

    assert [plan.scene_id for plan in plans] == [first["id"], second["id"]]
    assert plans[0].profile.style == "color_reveal"
    assert plans[0].profile.reveal_duration == 2.5
    assert plans[0].total_duration == 4.0
    assert plans[1].profile.style == "whiteboard"
    assert plans[1].profile.camera == "slow_zoom"
    assert plans[1].total_duration == 6.0


def test_scene_render_plan_keeps_all_visible_canvas_objects_and_media_sources(tmp_path):
    store = _store(tmp_path)
    scene = store.list_scenes("p1")[0]
    store.add_visual_object(scene["id"], "text", name="Title", payload={"text": "Hello"})
    store.add_visual_object(scene["id"], "drawing", name="Stroke", width=1280, height=720, payload={"points": [[1, 2], [3, 4]]})
    image_id = store.add_visual_object(scene["id"], "image", name="Photo", source="photo.png")
    store.add_visual_object(scene["id"], "video", name="Hidden video", source="hidden.mp4", visible=False)

    plan = build_scene_render_plan(store, "p1")[0]

    assert [obj["kind"] for obj in plan.objects] == ["text", "drawing", "image"]
    assert [obj["id"] for obj in plan.objects][-1] == image_id
    assert plan.media_sources == ("photo.png",)


def test_scene_render_plan_uses_custom_object_timing_for_total_duration(tmp_path):
    store = _store(tmp_path)
    scene = store.list_scenes("p1")[0]
    first = store.add_visual_object(scene["id"], "shape", name="One")
    second = store.add_visual_object(scene["id"], "text", name="Two", payload={"text": "Two"})
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=10.0,
        hold_duration=1.0,
        settings={
            "object_timing_mode": "custom",
            "outro_enabled": True,
            "outro_duration": 0.3,
            "custom_object_timing_config": [
                {"object_id": first, "pause": 0.5, "draw": 1.0, "push": 0.25},
                {"object_id": second, "pause": 0.0, "draw": 2.0, "push": 0.25},
            ],
        },
    )

    plan = build_scene_render_plan(store, "p1")[0]

    assert [(entry.object_id, entry.start, entry.end) for entry in plan.object_timing] == [
        (first, 0.0, 1.75),
        (second, 1.75, 4.0),
    ]
    assert plan.total_duration == 5.3


def test_scene_render_plan_without_objects_still_preserves_scene_duration(tmp_path):
    store = _store(tmp_path)
    scene = store.list_scenes("p1")[0]
    store.update_scene_render_settings(scene["id"], reveal_duration=3.0, hold_duration=1.0)

    plan = build_scene_render_plan(store, "p1")[0]

    assert plan.objects == ()
    assert plan.object_timing == ()
    assert plan.total_duration == 4.0
