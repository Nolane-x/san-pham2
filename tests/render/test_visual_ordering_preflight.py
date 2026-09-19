from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.compositor import (
    CompositionError,
    render_scene_layer_snapshot,
    validate_supported_static_visual_state,
)
from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import SceneVideoCompositor
from nolane_studio.render.whiteboard_compositor import WhiteboardSceneCompositor
from nolane_studio.storage.store import ProjectStore


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        raise AssertionError("FFmpeg runner must not execute before z-index preflight")


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        raise AssertionError("media exporter must not execute before z-index preflight")


def _object(object_id: str, z_index, *, kind: str = "shape", source: str = "", visible: bool = True):
    return {
        "id": object_id,
        "kind": kind,
        "source": source,
        "visible": visible,
        "z_index": z_index,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0 if kind != "video" else 640.0,
        "height": 180.0 if kind != "video" else 360.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {"fill": "#FF0000"} if kind == "shape" else {},
    }


def _plan(objects, *, style: str = "static", timing=()):
    return SceneRenderPlan(
        scene_id="ordering",
        position=0,
        text="Ordering preflight",
        objects=tuple(objects),
        profile=RenderProfile(
            style=style,
            camera="static",
            reveal_duration=0.5 if style == "whiteboard" else 0.0,
            hold_duration=1.0,
        ),
        object_timing=tuple(timing),
        total_duration=1.5 if style == "whiteboard" else 1.0,
        media_sources=(),
        render_config={},
    )


@pytest.mark.parametrize(
    "z_index",
    [float("inf"), float("-inf"), float("nan"), -1, 1.5, "1.5"],
)
def test_static_state_rejects_invalid_explicit_z_index(z_index):
    plan = _plan([_object("bad", z_index)])

    with pytest.raises(
        CompositionError,
        match=r"^scene ordering object bad z_index must be a non-negative integer$",
    ):
        validate_supported_static_visual_state(plan)


def test_static_state_rejects_duplicate_visible_z_index():
    plan = _plan([_object("first", 2), _object("second", 2)])

    with pytest.raises(
        CompositionError,
        match=r"^scene ordering visible z_index 2 must be unique$",
    ):
        validate_supported_static_visual_state(plan)


def test_static_state_allows_visible_gaps_and_ignores_hidden_ordering_collisions():
    plan = _plan(
        [
            _object("first", 0),
            _object("hidden", 2, visible=False),
            _object("second", 4),
        ]
    )

    validate_supported_static_visual_state(plan)


@pytest.mark.parametrize("bad_z", [float("nan"), 1.5])
def test_layer_snapshot_rejects_bad_z_index_before_output_side_effect(tmp_path, bad_z):
    plan = _plan([_object("bad", bad_z)])
    output = tmp_path / "snapshot-z" / "layer.png"

    with pytest.raises(CompositionError, match="z_index"):
        render_scene_layer_snapshot(
            plan,
            output,
            objects=plan.objects,
            transparent=False,
        )

    assert not output.parent.exists()


def test_whiteboard_rejects_duplicate_z_index_before_renderer_or_ffmpeg(tmp_path):
    objects = [_object("first", 1), _object("second", 1)]
    timing = (
        ObjectTimingEntry("first", start=0.0, pause=0.0, draw=0.5, push=0.0),
        ObjectTimingEntry("second", start=0.5, pause=0.0, draw=0.5, push=0.0),
    )
    plan = _plan(objects, style="whiteboard", timing=timing)
    render_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before z-index preflight")

    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-z" / "final.mp4"

    with pytest.raises(CompositionError, match=r"^scene ordering visible z_index 1 must be unique$"):
        compositor.render(plan, output)

    assert render_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


def test_video_rejects_nonintegral_z_index_before_probe_renderer_or_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    plan = _plan(
        [
            _object("back", 0),
            _object("video", 1.5, kind="video", source=str(source)),
        ]
    )
    render_calls: list[str] = []
    probe_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before z-index preflight")

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "video-z" / "final.mp4"

    with pytest.raises(
        CompositionError,
        match=r"^scene ordering object video z_index must be a non-negative integer$",
    ):
        compositor.render(plan, output)

    assert render_calls == []
    assert probe_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


def test_project_exporter_rejects_persisted_duplicate_z_index_before_output_side_effect(tmp_path):
    db_path = tmp_path / "studio.db"
    store = ProjectStore(db_path)
    store.initialize()
    store.create_project("p1", "Ordering")
    store.replace_scenes("p1", [Scene(0, "Only")])
    scene = store.list_scenes("p1")[0]
    first = store.add_visual_object(scene["id"], "shape", payload={"fill": "#FF0000"})
    second = store.add_visual_object(scene["id"], "text", payload={"text": "Second"})

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET z_index=0 WHERE id IN (?, ?)",
            (first, second),
        )

    media = RecordingMediaExporter()
    snapshot_calls: list[str] = []

    def snapshot_renderer(*args, **kwargs):
        del args, kwargs
        snapshot_calls.append("called")
        raise AssertionError("snapshot renderer must not execute before z-index preflight")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot_renderer,
    )
    output = tmp_path / "project-z" / "final.mp4"

    with pytest.raises(CompositionError, match=r"^scene .* visible z_index 0 must be unique$"):
        exporter.export("p1", output)

    assert snapshot_calls == []
    assert media.calls == []
    assert not output.parent.exists()
