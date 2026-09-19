from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import (
    SceneVideoCompositor,
    UnsupportedVideoComposition,
    validate_supported_video_composition,
)
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        del timeout
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def _video_plan(rotation: float) -> SceneRenderPlan:
    return SceneRenderPlan(
        scene_id="scene-video",
        position=0,
        text="Video scene",
        objects=(
            {
                "id": "video",
                "kind": "video",
                "source": "source.mp4",
                "rotation": rotation,
                "z_index": 0,
                "visible": True,
            },
        ),
        profile=RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0),
        object_timing=(),
        total_duration=1.0,
        media_sources=("source.mp4",),
    )


@pytest.mark.parametrize("rotation", [0.0, 90.0, -45.5, 1e300])
def test_video_rotation_preflight_accepts_finite_rotations(rotation):
    validate_supported_video_composition(_video_plan(rotation))


@pytest.mark.parametrize("rotation", [float("inf"), float("-inf")])
def test_video_rotation_preflight_rejects_nonfinite_rotations(rotation):
    with pytest.raises(UnsupportedVideoComposition, match=r"^video rotation must be finite$"):
        validate_supported_video_composition(_video_plan(rotation))


def test_project_exporter_preflights_later_nonfinite_video_rotation_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Non-finite video rotation preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=0.0,
        hold_duration=1.0,
        settings={"style": "static"},
    )

    source = tmp_path / "second-video.mp4"
    source.touch()
    second_object_id = store.add_visual_object(
        second["id"],
        "video",
        name="Second video",
        source=str(source),
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET rotation=? WHERE id=?",
            (float("inf"), second_object_id),
        )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.0,
        hold_duration=1.0,
        settings={"style": "static"},
    )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"png")
        return Path(output)

    runner = FakeRunner()
    layer_calls: list[str] = []

    def layer_renderer(plan, output, **kwargs):
        del kwargs
        layer_calls.append(plan.scene_id)
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: True,
        layer_renderer=layer_renderer,
    )

    def video(plan, output, **kwargs):
        render_calls.append(("video", plan.scene_id))
        return compositor.render(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
    )

    with pytest.raises(UnsupportedVideoComposition, match=r"^video rotation must be finite$"):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert layer_calls == []
    assert runner.commands == []
    assert media.calls == []
