from __future__ import annotations

from nolane_studio.render import effects


def test_render_profile_is_derived_from_recovered_scene_config():
    profile = effects.render_profile_from_config(
        {
            "style": "whiteboard",
            "visual_mode": "camera_motion",
            "reveal_duration": 2.5,
            "hold_duration": 1.25,
            "custom_camera_enabled": True,
            "custom_camera_config": [{"action": "zoom_in_out"}],
        }
    )

    assert profile.style == "whiteboard"
    assert profile.camera == "slow_zoom"
    assert profile.reveal_duration == 2.5
    assert profile.hold_duration == 1.25


def test_fixed_object_timing_preserves_reveal_total_and_skips_hidden_objects():
    objects = [
        {"id": "a", "visible": True},
        {"id": "hidden", "visible": False},
        {"id": "b", "visible": True},
    ]
    plan = effects.build_render_timing_plan(
        objects,
        {"object_timing_mode": "fixed", "reveal_duration": 6.0, "hold_duration": 2.0},
    )

    assert [entry.object_id for entry in plan] == ["a", "b"]
    assert [entry.draw for entry in plan] == [3.0, 3.0]
    assert [entry.start for entry in plan] == [0.0, 3.0]
    assert effects.estimate_object_timeline_seconds(plan, hold_duration=2.0) == 8.0


def test_custom_object_timing_uses_pause_draw_push_in_object_order():
    objects = [{"id": "a", "visible": True}, {"id": "b", "visible": True}]
    plan = effects.build_render_timing_plan(
        objects,
        {
            "object_timing_mode": "custom",
            "reveal_duration": 99.0,
            "custom_object_timing_config": [
                {"object_id": "a", "pause": 0.5, "draw": 1.25, "push": 0.25},
                {"object_id": "b", "pause": 0.0, "draw": 2.0, "push": 0.5},
            ],
        },
    )

    assert [(e.object_id, e.start, e.pause, e.draw, e.push, e.end) for e in plan] == [
        ("a", 0.0, 0.5, 1.25, 0.25, 2.0),
        ("b", 2.0, 0.0, 2.0, 0.5, 4.5),
    ]
    assert effects.estimate_object_timeline_seconds(plan, hold_duration=1.0, outro_duration=0.3) == 5.8


def test_custom_timing_missing_entry_fails_safe_to_fixed_share():
    objects = [{"id": "a", "visible": True}, {"id": "b", "visible": True}]
    plan = effects.build_render_timing_plan(
        objects,
        {
            "object_timing_mode": "custom",
            "reveal_duration": 4.0,
            "custom_object_timing_config": [{"object_id": "a", "draw": 1.0}],
        },
    )

    assert plan[0].draw == 1.0
    assert plan[1].draw == 2.0



def test_disabled_custom_camera_config_does_not_override_image_motion_config():
    profile = effects.render_profile_from_config(
        {
            "style": "whiteboard",
            "visual_mode": "camera_motion",
            "reveal_duration": 2.0,
            "hold_duration": 1.0,
            "custom_camera_enabled": False,
            "custom_camera_config": [{"action": "pan_left"}],
            "image_motion_config": {"action": "pan_right"},
        }
    )

    assert profile.camera == "pan_right"


def test_disabled_custom_camera_config_falls_back_to_default_camera_motion():
    profile = effects.render_profile_from_config(
        {
            "style": "whiteboard",
            "visual_mode": "camera_motion",
            "reveal_duration": 2.0,
            "hold_duration": 1.0,
            "custom_camera_enabled": False,
            "custom_camera_config": [{"action": "pan_left"}],
        }
    )

    assert profile.camera == "slow_zoom"
