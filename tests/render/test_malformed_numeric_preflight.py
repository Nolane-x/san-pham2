from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.compositor import (
    CompositionError,
    validate_supported_static_visual_state,
)
from nolane_studio.render.effects import ObjectTimingEntry, RenderProfile
from nolane_studio.render.project_export import (
    ProjectSceneExporter,
    validate_project_scene_composition,
)
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import (
    SceneVideoCompositor,
    UnsupportedVideoComposition,
    validate_supported_video_composition,
)
from nolane_studio.render.whiteboard_compositor import WhiteboardSceneCompositor
from nolane_studio.storage.store import ProjectStore


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        raise AssertionError("FFmpeg runner must not execute before malformed-numeric preflight")


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        raise AssertionError("media exporter must not execute before malformed-numeric preflight")


def _static_object(
    object_id: str = "static",
    *,
    kind: str = "shape",
    payload: dict[str, object] | None = None,
    **overrides,
) -> dict[str, object]:
    raw: dict[str, object] = {
        "id": object_id,
        "kind": kind,
        "visible": True,
        "z_index": 0,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": payload or ({"fill": "#FF0000"} if kind == "shape" else {}),
    }
    raw.update(overrides)
    return raw


def _plan(objects, *, style: str = "static", timing=()):
    return SceneRenderPlan(
        scene_id="malformed",
        position=0,
        text="Malformed numeric preflight",
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


@pytest.mark.parametrize("field", ["x", "y", "rotation"])
def test_static_geometry_rejects_nonnumeric_present_fields(field):
    plan = _plan([_static_object(**{field: "oops"})])

    with pytest.raises(
        CompositionError,
        match=rf"^scene malformed object static {field} must be finite$",
    ):
        validate_supported_static_visual_state(plan)


def test_static_geometry_preserves_numeric_strings_and_missing_defaults():
    raw = _static_object(x="1.25", y="-2.5", rotation="45")
    validate_supported_static_visual_state(_plan([raw]))

    missing = _static_object()
    missing.pop("x")
    missing.pop("y")
    missing.pop("rotation")
    validate_supported_static_visual_state(_plan([missing]))


@pytest.mark.parametrize(
    ("kind", "payload", "message"),
    [
        (
            "text",
            {"text": "Hello", "font_size": "oops"},
            "text font_size must be finite",
        ),
        (
            "drawing",
            {"points": [[0.0, 0.0], [1.0, 1.0]], "stroke": "oops"},
            "drawing stroke must be finite",
        ),
        (
            "drawing",
            {"points": [["oops", 0.0], [1.0, 1.0]], "stroke": 5.0},
            "drawing point 0 x must be finite",
        ),
        (
            "drawing",
            {"points": [[0.0, "oops"], [1.0, 1.0]], "stroke": 5.0},
            "drawing point 0 y must be finite",
        ),
    ],
)
def test_static_payload_rejects_nonnumeric_present_values(kind, payload, message):
    plan = _plan([_static_object(kind=kind, payload=payload)])

    with pytest.raises(
        CompositionError,
        match=rf"^scene malformed object static {message}$",
    ):
        validate_supported_static_visual_state(plan)


def test_static_payload_preserves_numeric_strings_and_missing_defaults():
    text = _static_object(
        "text",
        kind="text",
        payload={"text": "Hello", "font_size": "36.5"},
    )
    drawing = _static_object(
        "drawing",
        kind="drawing",
        payload={
            "points": [["1.25", "-2.5"], ["3", "4"]],
            "stroke": "5.5",
        },
        z_index=2,
    )
    validate_supported_static_visual_state(_plan([text, drawing]))

    text_missing = _static_object("text-missing", kind="text", payload={"text": "Hello"})
    drawing_missing = _static_object(
        "drawing-missing",
        kind="drawing",
        payload={"points": [[0.0, 0.0], [1.0, 1.0]]},
        z_index=3,
    )
    validate_supported_static_visual_state(_plan([text_missing, drawing_missing]))


@pytest.mark.parametrize("field", ["x", "y", "rotation"])
def test_video_composition_rejects_nonnumeric_present_geometry(tmp_path, field):
    source = tmp_path / "source.mp4"
    source.touch()
    video = {
        "id": "video",
        "kind": "video",
        "source": str(source),
        "visible": True,
        "z_index": 0,
        "x": 0.0,
        "y": 0.0,
        "width": 640.0,
        "height": 360.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {},
    }
    video[field] = "oops"

    with pytest.raises(
        UnsupportedVideoComposition,
        match=rf"^video {field} must be finite$",
    ):
        validate_supported_video_composition(_plan([video]))


def test_video_composition_preserves_numeric_strings_and_missing_defaults(tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    video = {
        "id": "video",
        "kind": "video",
        "source": str(source),
        "visible": True,
        "z_index": 0,
        "x": "1.25",
        "y": "-2.5",
        "width": "640",
        "height": "360",
        "rotation": "45",
        "opacity": "0.5",
        "payload": {},
    }
    validate_supported_video_composition(_plan([video]))

    missing = dict(video)
    missing.pop("x")
    missing.pop("y")
    missing.pop("rotation")
    validate_supported_video_composition(_plan([missing]))


def test_whiteboard_rejects_malformed_geometry_before_renderer_or_ffmpeg(tmp_path):
    raw = _static_object(x="oops")
    timing = (ObjectTimingEntry("static", start=0.0, pause=0.0, draw=0.5, push=0.0),)
    plan = _plan([raw], style="whiteboard", timing=timing)
    render_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before malformed-numeric preflight")

    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "whiteboard-malformed" / "final.mp4"

    with pytest.raises(
        CompositionError,
        match=r"^scene malformed object static x must be finite$",
    ):
        compositor.render(plan, output)

    assert render_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


def test_video_render_rejects_malformed_rotation_before_probe_renderer_or_ffmpeg(tmp_path):
    source = tmp_path / "source.mp4"
    source.touch()
    video = {
        "id": "video",
        "kind": "video",
        "source": str(source),
        "visible": True,
        "z_index": 0,
        "x": 0.0,
        "y": 0.0,
        "width": 640.0,
        "height": 360.0,
        "rotation": "oops",
        "opacity": 1.0,
        "payload": {},
    }
    plan = _plan([video])
    render_calls: list[str] = []
    probe_calls: list[str] = []
    runner = RecordingRunner()

    def layer_renderer(*args, **kwargs):
        del args, kwargs
        render_calls.append("called")
        raise AssertionError("layer renderer must not execute before malformed-numeric preflight")

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: probe_calls.append(path) or True,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "video-malformed" / "final.mp4"

    with pytest.raises(
        UnsupportedVideoComposition,
        match=r"^video rotation must be finite$",
    ):
        compositor.render(plan, output)

    assert render_calls == []
    assert probe_calls == []
    assert runner.commands == []
    assert not output.parent.exists()


def test_project_exporter_rejects_persisted_malformed_geometry_before_any_side_effect(tmp_path):
    db_path = tmp_path / "studio.db"
    store = ProjectStore(db_path)
    store.initialize()
    store.create_project("p1", "Malformed numeric")
    store.replace_scenes("p1", [Scene(0, "Only")])
    scene = store.list_scenes("p1")[0]
    object_id = store.add_visual_object(
        scene["id"],
        "shape",
        payload={"fill": "#FF0000"},
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET x='oops' WHERE id=?",
            (object_id,),
        )

    media = RecordingMediaExporter()
    snapshot_calls: list[str] = []

    def snapshot_renderer(*args, **kwargs):
        del args, kwargs
        snapshot_calls.append("called")
        raise AssertionError("snapshot renderer must not execute before malformed-numeric preflight")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot_renderer,
    )
    output = tmp_path / "project-malformed" / "final.mp4"

    with pytest.raises(
        CompositionError,
        match=rf"^scene {scene['id']} object {object_id} x must be finite$",
    ):
        exporter.export("p1", output)

    assert snapshot_calls == []
    assert media.calls == []
    assert not output.parent.exists()
