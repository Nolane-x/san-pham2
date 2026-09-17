from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.exporter import ExportClip, MediaExporter
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.whiteboard_compositor import WhiteboardSceneCompositor


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        raise AssertionError("FFmpeg runner must not execute before geometry preflight")


def _whiteboard_plan() -> SceneRenderPlan:
    timing = (
        ObjectTimingEntry(
            "shape-1",
            start=0.0,
            pause=0.1,
            draw=0.5,
            push=0.0,
        ),
    )
    return SceneRenderPlan(
        scene_id="scene-failfast",
        position=0,
        text="Geometry fail-fast",
        objects=(
            {
                "id": "shape-1",
                "kind": "shape",
                "visible": True,
                "z_index": 0,
                "payload": {"fill": "#FF0000"},
            },
        ),
        profile=RenderProfile(
            style="whiteboard",
            camera="static",
            reveal_duration=0.5,
            hold_duration=1.0,
        ),
        object_timing=timing,
        total_duration=1.6,
        media_sources=(),
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", float("inf"), "width must be finite"),
        ("height", float("-inf"), "height must be finite"),
        ("fps", float("nan"), "fps must be finite"),
    ],
)
def test_media_exporter_rejects_nonfinite_geometry_before_any_side_effect(
    tmp_path,
    field,
    value,
    message,
):
    probe_calls: list[str] = []
    runner = RecordingRunner()
    exporter = MediaExporter(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
    )
    output = tmp_path / "media-output" / "final.mp4"
    geometry = {"width": 1280, "height": 720, "fps": 24}
    geometry[field] = value

    with pytest.raises(ValueError, match=rf"^{message}$"):
        exporter.export(
            [ExportClip("video.mp4", "video")],
            output,
            **geometry,
        )

    assert probe_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_media_exporter_rejects_subunit_fps_before_any_side_effect(tmp_path, fps):
    probe_calls: list[str] = []
    runner = RecordingRunner()
    exporter = MediaExporter(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
    )
    output = tmp_path / "media-output" / "final.mp4"

    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        exporter.export(
            [ExportClip("video.mp4", "video")],
            output,
            fps=fps,
        )

    assert probe_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", float("inf"), "width must be finite"),
        ("height", float("-inf"), "height must be finite"),
        ("fps", float("nan"), "fps must be finite"),
    ],
)
def test_whiteboard_compositor_rejects_nonfinite_geometry_before_any_side_effect(
    tmp_path,
    field,
    value,
    message,
):
    render_calls: list[tuple[int, int]] = []
    runner = RecordingRunner()

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        render_calls.append((width, height))
        raise AssertionError("layer renderer must not execute before geometry preflight")

    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-output" / "final.mp4"
    geometry = {"width": 1280, "height": 720, "fps": 24}
    geometry[field] = value

    with pytest.raises(ValueError, match=rf"^{message}$"):
        compositor.render(
            _whiteboard_plan(),
            output,
            **geometry,
        )

    assert render_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_whiteboard_compositor_rejects_subunit_fps_before_any_side_effect(tmp_path, fps):
    render_calls: list[tuple[int, int]] = []
    runner = RecordingRunner()

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        render_calls.append((width, height))
        raise AssertionError("layer renderer must not execute before geometry preflight")

    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-output" / "final.mp4"

    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        compositor.render(
            _whiteboard_plan(),
            output,
            fps=fps,
        )

    assert render_calls == []
    assert runner.commands == []
    assert not output.parent.exists()
