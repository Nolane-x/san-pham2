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


def _plan(*, push: float = 0.0, push_direction: str | None = None) -> SceneRenderPlan:
    objects = (
        {"id": "a", "kind": "shape", "visible": True, "z_index": 0, "payload": {"fill": "#FF0000"}},
        {"id": "b", "kind": "text", "visible": True, "z_index": 1, "payload": {"text": "B"}},
    )
    timing = (
        ObjectTimingEntry("a", start=0.0, pause=0.5, draw=1.0, push=push),
        ObjectTimingEntry("b", start=1.5 + push, pause=0.25, draw=0.75, push=0.0),
    )
    total = timing[-1].end + 1.5
    kwargs = {}
    if push_direction is not None:
        kwargs["render_config"] = {"large_object_push_direction": push_direction}
    return SceneRenderPlan(
        scene_id="scene-wb",
        position=0,
        text="Whiteboard",
        objects=objects,
        profile=RenderProfile(style="whiteboard", reveal_duration=1.75, hold_duration=1.5),
        object_timing=timing,
        total_duration=total,
        media_sources=(),
        **kwargs,
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


def test_whiteboard_from_left_push_is_additive_and_preserves_pushed_object_state():
    plan = _plan(push=0.4, push_direction="from_left")
    segments = build_whiteboard_segments(plan)

    assert [(segment.kind, segment.duration) for segment in segments] == [
        ("hold", 0.5),
        ("reveal", 1.0),
        ("push", 0.4),
        ("hold", 0.25),
        ("reveal", 0.75),
        ("hold", 1.5),
    ]
    push_segment = segments[2]
    assert push_segment.before_ids == ("a",)
    assert push_segment.after_ids == ("a",)
    assert push_segment.object_id == "a"
    assert push_segment.direction == "from_left"
    assert segments[3].before_ids == ("a",)
    assert segments[4].after_ids == ("a", "b")
    assert sum(segment.duration for segment in segments) == pytest.approx(plan.total_duration)


def test_whiteboard_unknown_push_direction_fails_closed():
    with pytest.raises(UnsupportedWhiteboardMotion, match="direction"):
        build_whiteboard_segments(_plan(push=0.4, push_direction="diagonal"))


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


def test_whiteboard_renderer_pushes_object_from_left_and_keeps_final_state(tmp_path):
    plan = _plan(push=0.4, push_direction="from_left")
    rendered_states = []

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        rendered_states.append((tuple(obj["id"] for obj in objects), transparent))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    runner = FakeRunner()
    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-push.mp4"

    result = compositor.render(plan, output, width=1280, height=720, fps=24)

    assert result == output
    joined = [" ".join(command) for command in runner.commands]
    push_commands = [command for command in joined if "overlay=" in command and "1280" in command]
    assert len(push_commands) == 1
    assert "t/0.400000" in push_commands[0]
    assert "-1280" in push_commands[0]
    assert (("a",), True) in rendered_states
    assert rendered_states[-1][0] == ("a", "b")
