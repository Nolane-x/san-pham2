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


def _static_plan(
    *,
    kind: str = "shape",
    visible: bool = True,
    **geometry: float,
) -> SceneRenderPlan:
    obj: dict[str, object] = {
        "id": "static",
        "kind": kind,
        "x": -120.5,
        "y": -40.25,
        "width": 320.0,
        "height": 180.0,
        "rotation": -725.5,
        "opacity": 1.0,
        "z_index": 0,
        "visible": visible,
        "payload": {},
    }
    obj.update(geometry)
    return SceneRenderPlan(
        scene_id="scene-static",
        position=0,
        text="Static scene",
        objects=(obj,),
        profile=RenderProfile(style="static", reveal_duration=0.0, hold_duration=1.0),
        object_timing=(),
        total_duration=1.0,
        media_sources=(),
    )


@pytest.mark.parametrize("kind", ["shape", "text", "image", "drawing"])
def test_static_visual_geometry_preflight_accepts_finite_geometry(kind):
    validate_project_scene_composition(
        [
            _static_plan(
                kind=kind,
                x=-1e300,
                y=1e300,
                width=1e300,
                height=1e-300,
                rotation=-1e300,
            )
        ]
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("x", float("inf")),
        ("x", float("-inf")),
        ("y", float("inf")),
        ("y", float("-inf")),
        ("width", float("inf")),
        ("width", float("-inf")),
        ("height", float("inf")),
        ("height", float("-inf")),
        ("rotation", float("inf")),
        ("rotation", float("-inf")),
    ],
)
def test_static_visual_geometry_preflight_rejects_nonfinite_values(field, value):
    with pytest.raises(
        CompositionError,
        match=rf"^scene scene-static object static {field} must be finite$",
    ):
        validate_project_scene_composition([_static_plan(**{field: value})])


def test_static_visual_geometry_preflight_ignores_invisible_nonfinite_objects():
    validate_project_scene_composition(
        [_static_plan(visible=False, x=float("inf"), rotation=float("-inf"))]
    )


def test_project_exporter_preflights_later_nonfinite_static_geometry_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Non-finite static geometry preflight")
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
        "shape",
        name="Second shape",
        payload={"fill": "#00FF00"},
    )
    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET width=? WHERE id=?",
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
        match=rf"^scene {second['id']} object .* width must be finite$",
    ):
        try:
            exporter.export("p1", tmp_path / "never.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
