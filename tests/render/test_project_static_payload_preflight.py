from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.compositor import CompositionError
from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.project_export import (
    ProjectSceneExporter,
    validate_project_scene_composition,
)
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


def _plan(obj: dict[str, object]) -> SceneRenderPlan:
    return SceneRenderPlan(
        scene_id="scene-static",
        position=0,
        text="Static payload",
        objects=(obj,),
        profile=RenderProfile(style="static", hold_duration=1.0),
        object_timing=(),
        total_duration=1.0,
        media_sources=(),
        render_config={"style": "static"},
    )


def _drawing(*, points=None, stroke=5.0) -> dict[str, object]:
    return {
        "id": "drawing-1",
        "kind": "drawing",
        "visible": True,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {
            "points": [[1.0, 2.0], [3.0, 4.0]] if points is None else points,
            "stroke": stroke,
            "color": "#20232A",
        },
    }


def _text(*, font_size=36.0) -> dict[str, object]:
    return {
        "id": "text-1",
        "kind": "text",
        "visible": True,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {"text": "Hello", "font_size": font_size, "color": "#20232A"},
    }


@pytest.mark.parametrize("axis,index", [("x", 0), ("y", 1)])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_composition_preflight_rejects_nonfinite_drawing_point(axis, index, value):
    points = [[1.0, 2.0], [3.0, 4.0]]
    points[0][index] = value

    with pytest.raises(
        CompositionError,
        match=rf"^scene scene-static object drawing-1 drawing point 0 {axis} must be finite$",
    ):
        validate_project_scene_composition([_plan(_drawing(points=points))])


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_composition_preflight_rejects_nonfinite_drawing_stroke(value):
    with pytest.raises(
        CompositionError,
        match=r"^scene scene-static object drawing-1 drawing stroke must be finite$",
    ):
        validate_project_scene_composition([_plan(_drawing(stroke=value))])


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_composition_preflight_rejects_nonfinite_text_font_size(value):
    with pytest.raises(
        CompositionError,
        match=r"^scene scene-static object text-1 text font_size must be finite$",
    ):
        validate_project_scene_composition([_plan(_text(font_size=value))])


@pytest.mark.parametrize(
    "points",
    [
        "not-points",
        [1.0, 2.0],
        [[1.0], [2.0, 3.0]],
        [{"x": 1.0, "y": 2.0}, [3.0, 4.0]],
    ],
)
def test_composition_preflight_rejects_malformed_drawing_point_structure(points):
    with pytest.raises(
        CompositionError,
        match=r"^scene scene-static object drawing-1 drawing points must be coordinate pairs$",
    ):
        validate_project_scene_composition([_plan(_drawing(points=points))])


def test_composition_preflight_preserves_finite_static_payload_semantics():
    validate_project_scene_composition(
        [
            _plan(_drawing(points=[[-1e300, 1e300], [0.0, -1e300]], stroke=-5.0)),
            _plan(_text(font_size=-20.0)),
        ]
    )


def _store_with_later_nonfinite_drawing_payload(tmp_path) -> tuple[ProjectStore, str, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Static payload preflight")
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

    second_object_id = store.add_visual_object(
        second["id"],
        "drawing",
        name="Invalid persisted drawing",
        payload={
            "points": [[10.0, 20.0], [float("inf"), 40.0]],
            "stroke": 5.0,
            "color": "#20232A",
        },
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.0,
        hold_duration=1.0,
        settings={"style": "static"},
    )
    return store, second["id"], second_object_id


def test_project_exporter_rejects_later_nonfinite_static_payload_before_any_render(tmp_path):
    store, second_scene_id, second_object_id = _store_with_later_nonfinite_drawing_payload(tmp_path)
    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del output, kwargs
        render_calls.append(("video", plan.scene_id))
        raise AssertionError("video renderer must not be called")

    def whiteboard(plan, output, **kwargs):
        del output, kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        raise AssertionError("whiteboard renderer must not be called")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(
        CompositionError,
        match=(
            rf"^scene {second_scene_id} object {second_object_id} "
            r"drawing point 1 x must be finite$"
        ),
    ):
        try:
            exporter.export("p1", tmp_path / "never.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []



def test_composition_preflight_rejects_unknown_visible_object_kind():
    obj = {
        "id": "legacy-widget",
        "kind": "widget",
        "visible": True,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": {},
    }

    with pytest.raises(
        CompositionError,
        match=r"^scene scene-static contains unsupported visual object kind 'widget'$",
    ):
        validate_project_scene_composition([_plan(obj)])


def test_project_exporter_rejects_later_unknown_visible_object_kind_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "unknown-kind.db")
    store.initialize()
    store.create_project("p1", "Unknown object kind preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    second_object_id = store.add_visual_object(
        second["id"],
        "shape",
        name="Corrupt legacy object",
        payload={"fill": "#00AAFF"},
    )
    for scene in (first, second):
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.0,
            hold_duration=1.0,
            settings={"style": "whiteboard"},
        )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET kind=? WHERE id=?",
            ("widget", second_object_id),
        )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del output, kwargs
        render_calls.append(("video", plan.scene_id))
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        del kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(
        CompositionError,
        match=rf"^scene {second['id']} contains unsupported visual object kind 'widget'$",
    ):
        try:
            exporter.export("p1", tmp_path / "never-unknown-kind.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []



def test_composition_preflight_rejects_non_mapping_static_object_payload():
    obj = {
        "id": "text-corrupt-payload",
        "kind": "text",
        "visible": True,
        "x": 0.0,
        "y": 0.0,
        "width": 320.0,
        "height": 180.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "payload": [],
    }

    with pytest.raises(
        CompositionError,
        match=r"^scene scene-static object text-corrupt-payload payload must be a mapping$",
    ):
        validate_project_scene_composition([_plan(obj)])


def test_project_exporter_rejects_later_non_mapping_static_payload_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "payload-shape.db")
    store.initialize()
    store.create_project("p1", "Static payload shape preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    second_object_id = store.add_visual_object(
        second["id"],
        "text",
        name="Corrupt payload text",
        payload={"text": "Second"},
    )
    for scene in (first, second):
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.0,
            hold_duration=1.0,
            settings={"style": "whiteboard"},
        )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET payload_json=? WHERE id=?",
            ("[]", second_object_id),
        )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del kwargs
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        del kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(
        CompositionError,
        match=(
            rf"^scene {second['id']} object {second_object_id} "
            r"payload must be a mapping$"
        ),
    ):
        try:
            exporter.export("p1", tmp_path / "never-payload-shape.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
