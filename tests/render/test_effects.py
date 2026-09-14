from __future__ import annotations

from nolane_studio.render.effects import RenderProfile, build_image_filter_graph
from nolane_studio.render.exporter import build_video_segment_command


def test_whiteboard_profile_builds_progressive_reveal_over_white():
    profile = RenderProfile(style="whiteboard", reveal_duration=2.5, hold_duration=1.0)
    graph = build_image_filter_graph(1280, 720, 24, profile)
    assert "color=c=white" in graph
    assert "xfade=transition=wipeleft" in graph
    assert "duration=2.500000" in graph


def test_color_reveal_starts_grayscale_and_reveals_color():
    profile = RenderProfile(style="color_reveal", reveal_duration=1.75, hold_duration=0.5)
    graph = build_image_filter_graph(1280, 720, 24, profile)
    assert "hue=s=0" in graph
    assert "xfade=transition=wipeleft" in graph
    assert "duration=1.750000" in graph


def test_camera_motion_adds_zoompan_without_changing_output_contract():
    profile = RenderProfile(style="static", camera="slow_zoom", reveal_duration=0.0, hold_duration=4.0)
    graph = build_image_filter_graph(1280, 720, 24, profile)
    assert "zoompan=" in graph
    assert "s=1280x720" in graph
    assert "fps=24" in graph


def test_video_trim_and_speed_are_encoded_into_ffmpeg_command():
    cmd = build_video_segment_command(
        "ffmpeg",
        "clip.mp4",
        "scene.mp4",
        has_audio=True,
        trim_start=3.0,
        trim_end=13.0,
        speed=2.0,
    )
    joined = " ".join(cmd)
    assert "-ss 3.000000" in joined
    assert "-t 10.000000" in joined
    assert "setpts=PTS/2.000000" in joined
    assert "atempo=2.000000" in joined
