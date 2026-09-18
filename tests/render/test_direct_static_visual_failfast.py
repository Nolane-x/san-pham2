from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.render.compositor import CompositionError, render_scene_layer_snapshot
from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import SceneVideoCompositor
from nolane_studio.render.whiteboard_compositor import WhiteboardSceneCompositor


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        raise AssertionError("FFmpeg runner must not execute before static-state preflight")


_INVALID_STATIC_CASES = (
    ("x", {"kind": "shape", "x": float("inf")}, "scene direct-static object static-1 x must be finite"),
    ("y", {"kind": "shape", "y": float("-inf")}, "scene direct-static object static-1 y must be finite"),
    ("width", {"kind": "shape", "width": float("nan")}, "scene direct-static object static-1 width must be finite"),
    ("height", {"kind": "shape", "height": float("inf")}, "scene direct-static object static-1 height must be finite"),
    ("rotation", {"kind": "shape", "rotation": float("nan")}, "scene direct-static object static-1 rotation must be finite"),
    (
        "text-font-size",
        {"kind": "text", "payload": {"text": "bad", "font_size": float("inf")}},
        "scene direct-static object static-1 text font_size must be finite",
    ),
    (
        "drawing-stroke",
        {
            "kind": "drawing",
            "payload": {"stroke": float("nan"), "points": [[0.0, 0.0], [1.0, 1.0]]},
        },
        "scene direct-static object static-1 drawing stroke must be finite",
    ),
    (
        "drawing-point",
        {
            "kind": "drawing",
            "payload": {"stroke": 2.0, "points": [[float("inf"), 0.0], [1.0, 1.0]]},
        },
        "scene direct-static object static-1 drawing point 0 x must be finite",
    ),
    (
        "drawing-points-shape",
        {"kind": "drawing", "payload": {"stroke": 2.0, "points": "not-coordinate-pairs"}},
        "scene direct-static object static-1 drawing points must be coordinate pairs",
    ),
)


def _static_object(overrides):
    obj = {
        "id": "static-1",
        "kind": "shape",
        "visible": True,
        "z_index": 0,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {"fill": "#FF0000"},
    }
    obj.update(overrides)
    return obj


def _static_plan(obj, *, style="static", timing=()):
    return SceneRenderPlan(
        scene_id="direct-static",
        position=0,
        text="Direct static fail-fast",
        objects=(obj,),
        profile=RenderProfile(
            style=style,
            camera="static",
            reveal_duration=0.5 if style == "whiteboard" else 0.0,
            hold_duration=1.0,
        ),
        object_timing=timing,
        total_duration=1.5 if style == "whiteboard" else 1.0,
        media_sources=(),
        render_config={},
    )


@pytest.mark.parametrize(
    ("case_id", "overrides", "message"),
    _INVALID_STATIC_CASES,
    ids=[case[0] for case in _INVALID_STATIC_CASES],
)
def test_layer_snapshot_rejects_invalid_static_state_before_output_side_effect(
    tmp_path,
    case_id,
    overrides,
    message,
):
    del case_id
    obj = _static_object(overrides)
    plan = _static_plan(obj)
    output = tmp_path / "snapshot-output" / "layer.png"

    with pytest.raises(CompositionError, match=rf"^{message}$"):
        render_scene_layer_snapshot(
            plan,
            output,
            objects=plan.objects,
            transparent=False,
        )

    assert not output.parent.exists()


@pytest.mark.parametrize(
    ("case_id", "overrides", "message"),
    _INVALID_STATIC_CASES,
    ids=[case[0] for case in _INVALID_STATIC_CASES],
)
def test_whiteboard_rejects_invalid_static_state_before_any_side_effect(
    tmp_path,
    case_id,
    overrides,
    message,
):
    del case_id
    obj = _static_object(overrides)
    timing = (
        ObjectTimingEntry(
            "static-1",
            start=0.0,
            pause=0.0,
            draw=0.5,
            push=0.0,
        ),
    )
    plan = _static_plan(obj, style="whiteboard", timing=timing)
    render_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before static-state preflight")

    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-output" / "final.mp4"

    with pytest.raises(CompositionError, match=rf"^{message}$"):
        compositor.render(plan, output)

    assert render_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


@pytest.mark.parametrize(
    ("case_id", "overrides", "message"),
    _INVALID_STATIC_CASES,
    ids=[case[0] for case in _INVALID_STATIC_CASES],
)
def test_video_compositor_rejects_invalid_static_state_before_any_side_effect(
    tmp_path,
    case_id,
    overrides,
    message,
):
    del case_id
    source = tmp_path / "source.mp4"
    source.touch()
    static_obj = _static_object(overrides)
    video_obj = {
        "id": "video-1",
        "kind": "video",
        "source": str(source),
        "visible": True,
        "z_index": 1,
        "x": 0.0,
        "y": 0.0,
        "width": 640.0,
        "height": 360.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {},
    }
    plan = SceneRenderPlan(
        scene_id="direct-static",
        position=0,
        text="Direct video fail-fast",
        objects=(static_obj, video_obj),
        profile=RenderProfile(
            style="static",
            camera="static",
            reveal_duration=0.0,
            hold_duration=1.0,
        ),
        object_timing=(),
        total_duration=1.0,
        media_sources=(str(source),),
        render_config={},
    )
    render_calls: list[str] = []
    probe_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before static-state preflight")

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "video-output" / "final.mp4"

    with pytest.raises(CompositionError, match=rf"^{message}$"):
        compositor.render(plan, output)

    assert render_calls == []
    assert probe_calls == []
    assert runner.commands == []
    assert not output.parent.exists()
