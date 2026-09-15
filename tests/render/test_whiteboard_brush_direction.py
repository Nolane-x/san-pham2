from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage

from nolane_studio.render import whiteboard_compositor as whiteboard
from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.exporter import resolve_ffmpeg_exe
from nolane_studio.render.ffmpeg import SubprocessRunner
from nolane_studio.render.scene_plan import SceneRenderPlan


class FakeRunner:
    def __init__(self):
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def _plan(*, brush_mode: str) -> SceneRenderPlan:
    objects = (
        {
            "id": "shape",
            "kind": "shape",
            "visible": True,
            "z_index": 0,
            "payload": {"fill": "#7C5CFC"},
        },
    )
    timing = (ObjectTimingEntry("shape", start=0.0, pause=0.0, draw=0.25, push=0.0),)
    return SceneRenderPlan(
        scene_id="scene-brush",
        position=0,
        text="Brush direction",
        objects=objects,
        profile=RenderProfile(
            style="whiteboard",
            camera="static",
            reveal_duration=0.25,
            hold_duration=0.0,
        ),
        object_timing=timing,
        total_duration=0.25,
        media_sources=(),
        render_config={"brush_mode": brush_mode},
    )


def test_reveal_builder_exposes_recovered_brush_mode_contract():
    parameters = inspect.signature(whiteboard.build_object_reveal_command).parameters
    assert "brush_mode" in parameters, "whiteboard reveal builder must consume recovered brush_mode"

    left_to_right = " ".join(
        whiteboard.build_object_reveal_command(
            "ffmpeg",
            "before.png",
            "after.png",
            "lr.mp4",
            duration=0.4,
            brush_mode="lr",
        )
    )
    right_to_left = " ".join(
        whiteboard.build_object_reveal_command(
            "ffmpeg",
            "before.png",
            "after.png",
            "rl.mp4",
            duration=0.4,
            brush_mode="rl",
        )
    )

    assert "xfade=transition=wipeleft:duration=0.400000:offset=0" in left_to_right
    assert "xfade=transition=wiperight:duration=0.400000:offset=0" in right_to_left


def test_whiteboard_renderer_propagates_scene_brush_direction(tmp_path):
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
    output = tmp_path / "right-to-left.mp4"

    result = compositor.render(_plan(brush_mode="rl"), output, width=1280, height=720, fps=24)

    assert result == output
    joined = [" ".join(command) for command in runner.commands]
    reveal_commands = [command for command in joined if "xfade=transition=" in command]
    assert len(reveal_commands) == 1
    assert "xfade=transition=wiperight" in reveal_commands[0]
    assert "xfade=transition=wipeleft" not in reveal_commands[0]


def test_unknown_brush_mode_fails_closed(tmp_path):
    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    compositor = whiteboard.WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=FakeRunner(),
        layer_renderer=layer_renderer,
    )

    with pytest.raises(whiteboard.UnsupportedWhiteboardMotion, match="brush mode"):
        compositor.render(_plan(brush_mode="diagonal"), tmp_path / "never.mp4")


def test_real_ffmpeg_right_to_left_reveal_smoke(tmp_path):
    parameters = inspect.signature(whiteboard.build_object_reveal_command).parameters
    assert "brush_mode" in parameters, "whiteboard reveal builder must consume recovered brush_mode"

    width, height = 64, 36
    before = tmp_path / "before.png"
    after = tmp_path / "after.png"
    output = tmp_path / "reveal-rl.mp4"

    before_image = QImage(width, height, QImage.Format.Format_ARGB32)
    before_image.fill(QColor("white"))
    assert before_image.save(str(before))

    after_image = QImage(width, height, QImage.Format.Format_ARGB32)
    after_image.fill(QColor("#7C5CFC"))
    assert after_image.save(str(after))

    command = whiteboard.build_object_reveal_command(
        resolve_ffmpeg_exe(),
        str(before),
        str(after),
        str(output),
        duration=0.25,
        brush_mode="rl",
        width=width,
        height=height,
        fps=12,
    )
    SubprocessRunner().run(command, timeout=30)

    assert output.is_file()
    assert output.stat().st_size > 1000
