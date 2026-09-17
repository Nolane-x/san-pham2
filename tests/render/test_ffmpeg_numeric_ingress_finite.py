from __future__ import annotations

import math
import subprocess
import sys

import pytest

from nolane_studio.render.effects import (
    RenderProfile,
    build_camera_filter_chain,
    build_image_filter_graph,
)
from nolane_studio.render.exporter import (
    ExportClip,
    _atempo_filter,
    build_image_segment_command,
    build_transition_segment_command,
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


def _run_atempo_probe(literal: str, expected_message: str) -> None:
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
        pytest.fail("_atempo_filter did not return for invalid speed")

    assert result.returncode == 0
    assert result.stdout.strip() == expected_message


@pytest.mark.parametrize("literal", ["inf", "-inf", "nan"])
def test_atempo_filter_rejects_nonfinite_speed_without_hanging(literal):
    _run_atempo_probe(literal, "speed must be finite")


@pytest.mark.parametrize("literal", ["0.0", "-1.0"])
def test_atempo_filter_rejects_nonpositive_speed_without_hanging(literal):
    _run_atempo_probe(literal, "speed must be > 0")


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


@pytest.mark.parametrize("field", ["width", "height", "fps"])
@pytest.mark.parametrize("value", NONFINITE)
def test_video_segment_command_rejects_nonfinite_render_geometry(field, value):
    kwargs = {"width": 1280, "height": 720, "fps": 24}
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        build_video_segment_command(
            "ffmpeg",
            "clip.mp4",
            "out.mp4",
            has_audio=False,
            **kwargs,
        )


@pytest.mark.parametrize("field", ["width", "height", "fps"])
@pytest.mark.parametrize("value", NONFINITE)
def test_image_filter_graph_rejects_nonfinite_render_geometry(field, value):
    profile = RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0)
    kwargs = {"width": 1280, "height": 720, "fps": 24}
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        build_image_filter_graph(
            kwargs["width"],
            kwargs["height"],
            kwargs["fps"],
            profile,
        )


@pytest.mark.parametrize("field", ["width", "height", "fps"])
@pytest.mark.parametrize("value", NONFINITE)
def test_camera_filter_chain_rejects_nonfinite_render_geometry(field, value):
    kwargs = {"width": 1280, "height": 720, "fps": 24}
    kwargs[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        build_camera_filter_chain(
            kwargs["width"],
            kwargs["height"],
            kwargs["fps"],
            "slow_zoom",
        )


def _build_whiteboard_geometry_command(kind: str, **geometry):
    if kind == "reveal":
        return build_object_reveal_command(
            "ffmpeg",
            "before.png",
            "after.png",
            "out.mp4",
            duration=0.75,
            **geometry,
        )
    if kind == "push":
        return build_object_push_command(
            "ffmpeg",
            "base.png",
            "object.png",
            "out.mp4",
            duration=0.75,
            direction="from_left",
            **geometry,
        )
    return build_scene_outro_command(
        "ffmpeg",
        "scene.png",
        "out.mp4",
        duration=0.75,
        direction="left",
        **geometry,
    )


@pytest.mark.parametrize("kind", ["reveal", "push", "outro"])
@pytest.mark.parametrize("field", ["width", "height", "fps"])
@pytest.mark.parametrize("value", NONFINITE)
def test_whiteboard_commands_reject_nonfinite_render_geometry(kind, field, value):
    geometry = {"width": 1280, "height": 720, "fps": 24}
    geometry[field] = value

    with pytest.raises(ValueError, match=rf"^{field} must be finite$"):
        _build_whiteboard_geometry_command(kind, **geometry)


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_video_segment_command_rejects_fps_below_one(fps):
    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        build_video_segment_command(
            "ffmpeg",
            "clip.mp4",
            "out.mp4",
            has_audio=False,
            fps=fps,
        )


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_effect_filter_builders_reject_fps_below_one(fps):
    profile = RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0)

    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        build_camera_filter_chain(1280, 720, fps, "slow_zoom")
    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        build_image_filter_graph(1280, 720, fps, profile)


@pytest.mark.parametrize("kind", ["reveal", "push", "outro"])
@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_whiteboard_commands_reject_fps_below_one(kind, fps):
    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        _build_whiteboard_geometry_command(kind, width=1280, height=720, fps=fps)


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_transition_command_rejects_fps_below_one(fps):
    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        build_transition_segment_command(
            "ffmpeg",
            "left.mp4",
            "right.mp4",
            "out.mp4",
            fps=fps,
        )


def test_finite_render_dimensions_preserve_existing_clamp_and_even_normalization():
    video = build_video_segment_command(
        "ffmpeg",
        "clip.mp4",
        "video.mp4",
        has_audio=False,
        width=-9,
        height=7,
        fps=24,
    )
    profile = RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0)
    graph = build_image_filter_graph(-9, 7, 24, profile)
    push = build_object_push_command(
        "ffmpeg",
        "base.png",
        "object.png",
        "push.mp4",
        duration=0.75,
        direction="from_left",
        width=-9,
        height=7,
        fps=24,
    )

    assert any("scale=2:6:" in part and "pad=2:6:" in part for part in video)
    assert "scale=2:6:" in graph and "pad=2:6:" in graph
    assert any("scale=2:6" in part for part in push)


def test_large_finite_render_dimensions_are_not_capped():
    width = 1_000_001
    height = 1_000_003
    video = build_video_segment_command(
        "ffmpeg",
        "clip.mp4",
        "video.mp4",
        has_audio=False,
        width=width,
        height=height,
        fps=24,
    )

    assert any(
        "scale=1000000:1000002:" in part and "pad=1000000:1000002:" in part
        for part in video
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
