from __future__ import annotations

from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.exporter import build_image_segment_command


def test_effect_profile_does_not_override_authoritative_scene_duration():
    profile = RenderProfile(
        style="whiteboard",
        camera="static",
        reveal_duration=2.0,
        hold_duration=1.0,
    )

    cmd = build_image_segment_command(
        "ffmpeg",
        "scene.png",
        "scene.mp4",
        duration=5.0,
        profile=profile,
    )
    joined = " ".join(cmd)

    assert "-t 5.000000" in joined
    assert "trim=duration=5.000000" in joined
    assert "xfade=transition=wipeleft:duration=2.000000" in joined
