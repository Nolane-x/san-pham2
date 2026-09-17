from __future__ import annotations

import math

import pytest

from nolane_studio.render.effects import RenderProfile, build_image_filter_graph
from nolane_studio.render.exporter import ExportClip, build_image_segment_command
from nolane_studio.render.whiteboard_compositor import (
    WhiteboardSegment,
    build_object_push_command,
    build_object_reveal_command,
    build_scene_outro_command,
)


NONFINITE = [float("inf"), float("-inf"), float("nan")]


@pytest.mark.parametrize("value", NONFINITE)
def test_image_export_clip_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^image duration must be finite$"):
        ExportClip(path="frame.png", kind="image", duration=value)


@pytest.mark.parametrize("value", NONFINITE)
def test_image_segment_command_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^duration must be finite$"):
        build_image_segment_command(
            "ffmpeg",
            "frame.png",
            "out.mp4",
            duration=value,
        )


@pytest.mark.parametrize("value", NONFINITE)
def test_image_filter_graph_rejects_nonfinite_total_duration(value):
    profile = RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0)

    with pytest.raises(ValueError, match=r"^total_duration must be finite$"):
        build_image_filter_graph(
            1280,
            720,
            24,
            profile,
            total_duration=value,
        )


@pytest.mark.parametrize("value", NONFINITE)
def test_whiteboard_segment_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^whiteboard segment duration must be finite$"):
        WhiteboardSegment(
            kind="hold",
            duration=value,
            before_ids=(),
            after_ids=(),
        )


@pytest.mark.parametrize("value", NONFINITE)
def test_object_reveal_command_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^reveal duration must be finite$"):
        build_object_reveal_command(
            "ffmpeg",
            "before.png",
            "after.png",
            "out.mp4",
            duration=value,
        )


@pytest.mark.parametrize("value", NONFINITE)
def test_object_push_command_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^push duration must be finite$"):
        build_object_push_command(
            "ffmpeg",
            "base.png",
            "object.png",
            "out.mp4",
            duration=value,
            direction="from_left",
        )


@pytest.mark.parametrize("value", NONFINITE)
def test_scene_outro_command_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^outro duration must be finite$"):
        build_scene_outro_command(
            "ffmpeg",
            "scene.png",
            "out.mp4",
            duration=value,
            direction="left",
        )


def test_finite_low_level_ffmpeg_durations_preserve_existing_behavior():
    duration = 0.75
    clip = ExportClip(path="frame.png", kind="image", duration=duration)
    profile = RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0)

    image_command = build_image_segment_command(
        "ffmpeg",
        clip.path,
        "image.mp4",
        duration=clip.duration,
        profile=profile,
    )
    graph = build_image_filter_graph(
        1280,
        720,
        24,
        profile,
        total_duration=duration,
    )
    segment = WhiteboardSegment(
        kind="hold",
        duration=duration,
        before_ids=(),
        after_ids=(),
    )
    reveal = build_object_reveal_command(
        "ffmpeg",
        "before.png",
        "after.png",
        "reveal.mp4",
        duration=duration,
    )
    push = build_object_push_command(
        "ffmpeg",
        "base.png",
        "object.png",
        "push.mp4",
        duration=duration,
        direction="from_left",
    )
    outro = build_scene_outro_command(
        "ffmpeg",
        "scene.png",
        "outro.mp4",
        duration=duration,
        direction="left",
    )

    assert clip.duration == duration
    assert segment.duration == duration
    for text in [*image_command, graph, *reveal, *push, *outro]:
        lowered = str(text).lower()
        assert "nan" not in lowered
        assert "inf" not in lowered
    assert math.isfinite(segment.duration)
