from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.render import whiteboard_compositor as whiteboard
from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.scene_plan import SceneRenderPlan


class FakeRunner:
    def __init__(self):
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def _plan(
    *,
    outro_enabled: bool = False,
    outro_direction: str = "left",
    outro_duration: float = 0.4,
) -> SceneRenderPlan:
    objects = (
        {"id": "a", "kind": "shape", "visible": True, "z_index": 0, "payload": {"fill": "#FF0000"}},
        {"id": "b", "kind": "text", "visible": True, "z_index": 1, "payload": {"text": "B"}},
    )
    timing = (
        ObjectTimingEntry("a", start=0.0, pause=0.5, draw=1.0, push=0.0),
        ObjectTimingEntry("b", start=1.5, pause=0.25, draw=0.75, push=0.0),
    )
    hold_duration = 1.5
    total = timing[-1].end + hold_duration + (outro_duration if outro_enabled else 0.0)
    return SceneRenderPlan(
        scene_id="scene-outro",
        position=0,
        text="Outro",
        objects=objects,
        profile=RenderProfile(
            style="whiteboard",
            camera="static",
            reveal_duration=1.75,
            hold_duration=hold_duration,
        ),
        object_timing=timing,
        total_duration=total,
        media_sources=(),
        render_config={
            "outro_enabled": outro_enabled,
            "outro_direction": outro_direction,
            "outro_duration": outro_duration,
        },
    )


def test_disabled_outro_keeps_existing_final_hold_contract():
    segments = whiteboard.build_whiteboard_segments(_plan())

    assert [(segment.kind, segment.duration) for segment in segments][-1] == ("hold", 1.5)
    assert all(segment.kind != "outro" for segment in segments)


def test_enabled_left_outro_is_a_distinct_additive_phase_after_final_hold():
    plan = _plan(outro_enabled=True, outro_direction="left", outro_duration=0.4)
    segments = whiteboard.build_whiteboard_segments(plan)

    assert [(segment.kind, segment.duration) for segment in segments][-2:] == [
        ("hold", 1.5),
        ("outro", 0.4),
    ]
    assert segments[-1].before_ids == ("a", "b")
    assert segments[-1].after_ids == ("a", "b")
    assert segments[-1].direction == "left"
    assert sum(segment.duration for segment in segments) == pytest.approx(plan.total_duration)


def test_unknown_outro_direction_fails_closed_instead_of_becoming_hold():
    with pytest.raises(whiteboard.UnsupportedWhiteboardMotion, match="outro direction"):
        whiteboard.build_whiteboard_segments(
            _plan(outro_enabled=True, outro_direction="diagonal", outro_duration=0.4)
        )


def test_left_outro_command_moves_whole_scene_off_canvas():
    builder = getattr(whiteboard, "build_scene_outro_command", None)
    assert builder is not None, "whiteboard outro needs its own recovered motion command"

    command = builder(
        "ffmpeg",
        "scene.png",
        "outro.mp4",
        duration=0.4,
        direction="left",
        width=1280,
        height=720,
        fps=24,
    )
    joined = " ".join(command)
    assert "overlay=" in joined
    assert "-1280*min(t/0.400000,1)" in joined
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in joined
    assert "-t 0.400000" in joined


def test_whiteboard_renderer_uses_outro_motion_segment_not_static_hold(tmp_path):
    plan = _plan(outro_enabled=True, outro_direction="left", outro_duration=0.4)

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    runner = FakeRunner()
    compositor = whiteboard.WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-outro.mp4"

    result = compositor.render(plan, output, width=1280, height=720, fps=24)

    assert result == output
    joined = [" ".join(command) for command in runner.commands]
    outro_commands = [command for command in joined if "overlay=" in command and "t/0.400000" in command]
    assert len(outro_commands) == 1
    assert "-1280*min(t/0.400000,1)" in outro_commands[0]
    assert runner.commands[-1][-1] == str(output)
