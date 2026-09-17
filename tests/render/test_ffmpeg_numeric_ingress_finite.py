from __future__ import annotations

import math
import subprocess
import sys

import pytest

from nolane_studio.render.effects import RenderProfile, build_image_filter_graph
from nolane_studio.render.exporter import (
    ExportClip,
    _atempo_filter,
    build_image_segment_command,
    build_video_segment_command,
)
from nolane_studio.render.whiteboard_compositor import (
    WhiteboardSegment,
    build_object_push_command,
    build_object_reveal_command,
    build_scene_camera_command,
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


@pytest.mark.parametrize("field", ["trim_start", "trim_end", "speed"])
@pytest.mark.parametrize("value", NONFINITE)
def test_video_export_clip_rejects_nonfinite_controls(field, value):
    kwargs = {"trim_start": 0.25, "trim_end": 2.0, "speed": 1.0}
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        ExportClip(path="clip.mp4", kind="video", **kwargs)


@pytest.mark.parametrize("field", ["trim_start", "trim_end", "speed"])
@pytest.mark.parametrize("value", NONFINITE)
def test_video_segment_command_rejects_nonfinite_controls(field, value):
    kwargs = {"trim_start": 0.25, "trim_end": 2.0, "speed": 1.0}
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        build_video_segment_command(
            "ffmpeg",
            "clip.mp4",
            "out.mp4",
            has_audio=False,
            **kwargs,
        )


@pytest.mark.parametrize("literal", ["inf", "-inf", "nan"])
def test_atempo_filter_rejects_nonfinite_speed_without_hanging(literal):
    code = (
        "from nolane_studio.render.exporter import _atempo_filter\n"
        f"value = float({literal!r})\n"
        "try:\n"
        "    _atempo_filter(value)\n"
        "except ValueError as exc:\n"
        "    print(str(exc))\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(3)\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=3.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("_atempo_filter did not return for non-finite speed")

    assert result.returncode == 0
    assert result.stdout.strip() == "speed must be finite"


@pytest.mark.parametrize("value", NONFINITE)
def test_scene_camera_command_rejects_nonfinite_duration(value):
    with pytest.raises(ValueError, match=r"^camera duration must be finite$"):
        build_scene_camera_command(
            "ffmpeg",
            "scene.mp4",
            "out.mp4",
            camera="slow_zoom",
            duration=value,
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


def test_finite_video_and_camera_controls_preserve_existing_behavior():
    clip = ExportClip(
        path="clip.mp4",
        kind="video",
        trim_start=0.25,
        trim_end=2.0,
        speed=1.5,
    )
    video = build_video_segment_command(
        "ffmpeg",
        clip.path,
        "video.mp4",
        has_audio=True,
        trim_start=clip.trim_start,
        trim_end=clip.trim_end,
        speed=clip.speed,
    )
    camera = build_scene_camera_command(
        "ffmpeg",
        "scene.mp4",
        "camera.mp4",
        camera="slow_zoom",
        duration=1.75,
    )

    assert _atempo_filter(4.0) == "atempo=2.000000,atempo=2.000000"
    assert "-ss" in video and "0.250000" in video
    assert "-t" in video and "1.750000" in video
    assert any("setpts=PTS/1.500000" in part for part in video)
    assert "atempo=1.500000" in video
    for text in [*video, *camera]:
        lowered = str(text).lower()
        assert "nan" not in lowered
        assert "inf" not in lowered
