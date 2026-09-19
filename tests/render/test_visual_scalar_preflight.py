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
from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import SceneVideoCompositor, validate_supported_video_composition
from nolane_studio.storage.store import ProjectStore


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        raise AssertionError("FFmpeg runner must not execute before scalar-state preflight")


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        raise AssertionError("media exporter must not execute before scalar-state preflight")


def _object(
    object_id: str,
    *,
    kind: str = "shape",
    source: str = "",
    width: float = 320.0,
    height: float = 180.0,
    opacity: float = 1.0,
):
    return {
        "id": object_id,
        "kind": kind,
        "source": source,
        "visible": True,
        "z_index": 0,
        "x": 0.0,
        "y": 0.0,
        "width": width,
        "height": height,
        "rotation": 0.0,
        "opacity": opacity,
        "payload": {"fill": "#FF0000"} if kind == "shape" else {},
    }


def _plan(objects):
    return SceneRenderPlan(
        scene_id="scalar",
        position=0,
        text="Scalar preflight",
        objects=tuple(objects),
        profile=RenderProfile(
            style="static",
            camera="static",
            reveal_duration=0.0,
            hold_duration=1.0,
        ),
        object_timing=(),
        total_duration=1.0,
        media_sources=(),
        render_config={},
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", 0.0, "width must be > 0"),
        ("width", -1.0, "width must be > 0"),
        ("height", 0.0, "height must be > 0"),
        ("height", -1.0, "height must be > 0"),
        ("width", "oops", "width must be finite"),
        ("opacity", float("inf"), "opacity must be finite"),
        ("opacity", float("-inf"), "opacity must be finite"),
        ("opacity", float("nan"), "opacity must be finite"),
        ("opacity", -0.01, "opacity must be within 0..1"),
        ("opacity", 1.01, "opacity must be within 0..1"),
        ("opacity", "oops", "opacity must be finite"),
    ],
)
def test_static_state_rejects_invalid_persisted_scalar_domain(field, value, message):
    raw = _object("bad")
    raw[field] = value
    plan = _plan([raw])

    with pytest.raises(
        CompositionError,
        match=rf"^scene scalar object bad {message}$",
    ):
        validate_supported_static_visual_state(plan)


def test_static_state_accepts_positive_dimensions_and_opacity_boundaries():
    plan = _plan(
        [
            _object("transparent", width=0.25, height=0.5, opacity=0.0),
            {
                **_object("opaque", width=1.0, height=2.0, opacity=1.0),
                "z_index": 2,
            },
        ]
    )

    validate_supported_static_visual_state(plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("width", 0.0),
        ("height", -1.0),
        ("opacity", float("nan")),
        ("opacity", 1.5),
    ],
)
def test_layer_snapshot_rejects_invalid_scalar_before_output_side_effect(tmp_path, field, value):
    raw = _object("bad")
    raw[field] = value
    plan = _plan([raw])
    output = tmp_path / "scalar-snapshot" / "layer.png"

    with pytest.raises(CompositionError):
        render_scene_layer_snapshot(
            plan,
            output,
            objects=plan.objects,
            transparent=False,
        )

    assert not output.parent.exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", 0.0, "width must be > 0"),
        ("height", -1.0, "height must be > 0"),
        ("width", "oops", "width must be finite"),
        ("opacity", float("inf"), "opacity must be finite"),
        ("opacity", float("nan"), "opacity must be finite"),
        ("opacity", -0.1, "opacity must be within 0..1"),
        ("opacity", 1.1, "opacity must be within 0..1"),
        ("opacity", "oops", "opacity must be finite"),
    ],
)
def test_video_composition_rejects_invalid_scalar_domain(tmp_path, field, value, message):
    source = tmp_path / "source.mp4"
    source.touch()
    raw = _object("video", kind="video", source=str(source), width=640.0, height=360.0)
    raw[field] = value
    plan = _plan([raw])

    with pytest.raises(
        CompositionError,
        match=rf"^scene scalar object video {message}$",
    ):
        validate_supported_video_composition(plan)


def test_video_render_rejects_invalid_opacity_before_probe_renderer_or_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    plan = _plan([_object("video", kind="video", source=str(source), width=640.0, height=360.0, opacity=float("nan"))])
    runner = RecordingRunner()
    probe_calls: list[str] = []
    renderer_calls: list[str] = []

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        renderer_calls.append("called")
        raise AssertionError("layer renderer must not execute before scalar-state preflight")

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "scalar-video" / "final.mp4"

    with pytest.raises(
        CompositionError,
        match=r"^scene scalar object video opacity must be finite$",
    ):
        compositor.render(plan, output)

    assert probe_calls == []
    assert renderer_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


def test_project_exporter_rejects_corrupt_scalar_state_before_output_side_effect(tmp_path):
    db_path = tmp_path / "studio.db"
    store = ProjectStore(db_path)
    store.initialize()
    store.create_project("p1", "Scalar")
    store.replace_scenes("p1", [Scene(0, "Only")])
    scene = store.list_scenes("p1")[0]
    object_id = store.add_visual_object(
        scene["id"],
        "shape",
        width=320.0,
        height=180.0,
        opacity=1.0,
        payload={"fill": "#FF0000"},
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA ignore_check_constraints = ON")
        conn.execute(
            "UPDATE visual_editor_objects SET width=-1, opacity=2 WHERE id=?",
            (object_id,),
        )

    media = RecordingMediaExporter()
    snapshot_calls: list[str] = []

    def snapshot_renderer(*args, **kwargs):
        del args, kwargs
        snapshot_calls.append("called")
        raise AssertionError("snapshot renderer must not execute before scalar-state preflight")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot_renderer,
    )
    output = tmp_path / "scalar-project" / "final.mp4"

    with pytest.raises(CompositionError, match=r"^scene .* object .* width must be > 0$"):
        exporter.export("p1", output)

    assert snapshot_calls == []
    assert media.calls == []
    assert not output.parent.exists()
