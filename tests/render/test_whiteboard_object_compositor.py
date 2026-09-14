from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.whiteboard_compositor import (
    UnsupportedWhiteboardMotion,
    WhiteboardSceneCompositor,
    build_whiteboard_segments,
)


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def _plan(*, push: float = 0.0) -> SceneRenderPlan:
    objects = (
        {"id": "a", "kind": "shape", "visible": True, "z_index": 0, "payload": {"fill": "#FF0000"}},
        {"id": "b", "kind": "text", "visible": True, "z_index": 1, "payload": {"text": "B"}},
    )
    timing = (
        ObjectTimingEntry("a", start=0.0, pause=0.5, draw=1.0, push=push),
        ObjectTimingEntry("b", start=1.5 + push, pause=0.25, draw=0.75, push=0.0),
    )
    total = timing[-1].end + 1.5
    return SceneRenderPlan(
        scene_id="scene-wb",
        position=0,
        text="Whiteboard",
        objects=objects,
        profile=RenderProfile(style="whiteboard", reveal_duration=1.75, hold_duration=1.5),
        object_timing=timing,
        total_duration=total,
        media_sources=(),
    )


def test_whiteboard_segments_preserve_per_object_pause_draw_and_final_hold():
    segments = build_whiteboard_segments(_plan())

    assert [(segment.kind, segment.duration) for segment in segments] == [
        ("hold", 0.5),
        ("reveal", 1.0),
        ("hold", 0.25),
        ("reveal", 0.75),
        ("hold", 1.5),
    ]
    assert segments[0].before_ids == () and segments[0].after_ids == ()
    assert segments[1].before_ids == () and segments[1].after_ids == ("a",)
    assert segments[2].before_ids == ("a",) and segments[2].after_ids == ("a",)
    assert segments[3].before_ids == ("a",) and segments[3].after_ids == ("a", "b")
    assert segments[4].after_ids == ("a", "b")
    assert sum(segment.duration for segment in segments) == pytest.approx(_plan().total_duration)


def test_whiteboard_push_phase_fails_closed_until_motion_renderer_exists():
    with pytest.raises(UnsupportedWhiteboardMotion, match="push"):
        build_whiteboard_segments(_plan(push=0.4))


def test_whiteboard_renderer_uses_cumulative_snapshots_and_additive_segments(tmp_path):
    plan = _plan()
    rendered_states = []

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        rendered_states.append(tuple(obj["id"] for obj in objects))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    runner = FakeRunner()
    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard.mp4"

    result = compositor.render(plan, output, width=1280, height=720, fps=24)

    assert result == output
    assert rendered_states == [(), ("a",), ("a", "b")]
    joined = [" ".join(command) for command in runner.commands]
    assert any("xfade=transition=wipeleft:duration=1.000000" in command for command in joined)
    assert any("xfade=transition=wipeleft:duration=0.750000" in command for command in joined)
    assert sum(" -f concat " in f" {command} " for command in joined) == 1
    assert runner.commands[-1][-1] == str(output)
