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


def _plan_with_blank_id() -> SceneRenderPlan:
    return SceneRenderPlan(
        scene_id="scene-blank-id",
        position=0,
        text="Blank object identity",
        objects=(
            {
                "id": "",
                "kind": "shape",
                "visible": True,
                "x": 0.0,
                "y": 0.0,
                "width": 320.0,
                "height": 180.0,
                "rotation": 0.0,
                "opacity": 1.0,
                "z_index": 0,
                "payload": {"fill": "#FF0000"},
            },
        ),
        profile=RenderProfile(style="static", hold_duration=1.0),
        object_timing=(),
        total_duration=1.0,
        media_sources=(),
        render_config={"style": "static"},
    )


def test_composition_preflight_rejects_visible_object_with_blank_id():
    with pytest.raises(
        CompositionError,
        match=r"^scene scene-blank-id contains visible object with blank id$",
    ):
        validate_project_scene_composition([_plan_with_blank_id()])


def test_project_exporter_rejects_later_blank_object_id_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "blank-object-id.db")
    store.initialize()
    store.create_project("p1", "Blank object identity preflight")
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
        name="Corrupt blank identity",
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
            "UPDATE visual_editor_objects SET id='' WHERE id=?",
            (second_object_id,),
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
        match=rf"^scene {second['id']} contains visible object with blank id$",
    ):
        try:
            exporter.export("p1", tmp_path / "never-blank-id.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []



def test_composition_preflight_rejects_visible_object_id_with_surrounding_whitespace():
    plan = _plan_with_blank_id()
    obj = dict(plan.objects[0])
    obj["id"] = "  object-1  "
    plan = SceneRenderPlan(
        scene_id="scene-noncanonical-object-id",
        position=0,
        text=plan.text,
        objects=(obj,),
        profile=plan.profile,
        object_timing=plan.object_timing,
        total_duration=plan.total_duration,
        media_sources=plan.media_sources,
        render_config=plan.render_config,
    )

    with pytest.raises(
        CompositionError,
        match=(
            r"^scene scene-noncanonical-object-id contains visible object "
            r"with noncanonical id '  object-1  '$"
        ),
    ):
        validate_project_scene_composition([plan])


def test_project_exporter_rejects_later_object_id_with_surrounding_whitespace_before_any_render(
    tmp_path,
):
    store = ProjectStore(tmp_path / "noncanonical-object-id.db")
    store.initialize()
    store.create_project("p1", "Canonical object identity preflight")
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
        name="Noncanonical identity",
        payload={"fill": "#00AAFF"},
    )
    for scene in (first, second):
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.0,
            hold_duration=1.0,
            settings={"style": "whiteboard"},
        )

    corrupt_id = f"  {second_object_id}  "
    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET id=? WHERE id=?",
            (corrupt_id, second_object_id),
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
            rf"^scene {second['id']} contains visible object "
            rf"with noncanonical id '  {second_object_id}  '$"
        ),
    ):
        try:
            exporter.export("p1", tmp_path / "never-noncanonical-object-id.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
