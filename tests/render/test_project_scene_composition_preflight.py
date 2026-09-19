from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.whiteboard_compositor import UnsupportedWhiteboardMotion
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


def test_project_exporter_preflights_later_unsupported_scene_composition_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Composition preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(first["id"], "shape", name="First shape", payload={"fill": "#FF0000"})
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "whiteboard"},
    )

    video_source = tmp_path / "second.mp4"
    video_source.touch()
    store.add_visual_object(second["id"], "video", name="Second video", source=str(video_source))
    store.add_visual_object(second["id"], "text", name="Second text", payload={"text": "Overlay"})
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "whiteboard"},
    )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"png")
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        del kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del kwargs
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
        video_renderer=video,
    )

    with pytest.raises(UnsupportedWhiteboardMotion, match="source-video"):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []



@pytest.mark.parametrize("stored_kind", [" Shape ", "IMAGE", "widget"])
def test_visual_object_reader_rejects_noncanonical_persisted_kind(tmp_path, stored_kind):
    store = ProjectStore(tmp_path / "kind-reader.db")
    store.initialize()
    store.create_project("p1", "Kind reader")
    store.replace_scenes("p1", [Scene(0, "Only")])
    scene = store.list_scenes("p1")[0]
    object_id = store.add_visual_object(scene["id"], "shape", name="Kind integrity")

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET kind=? WHERE id=?",
            (stored_kind, object_id),
        )

    with pytest.raises(
        ValueError,
        match=(
            rf"^visual object {object_id} kind must be stored canonically as one of: "
            r"drawing, image, shape, text, video$"
        ),
    ):
        store.list_visual_objects(scene["id"])


def test_project_exporter_rejects_later_noncanonical_object_kind_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "kind-preflight.db")
    store.initialize()
    store.create_project("p1", "Canonical kind preflight")
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
        name="Corrupt kind",
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
            (" Shape ", second_object_id),
        )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        del kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del kwargs
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
        video_renderer=video,
    )

    with pytest.raises(
        ValueError,
        match=(
            rf"^visual object {second_object_id} kind must be stored canonically as one of: "
            r"drawing, image, shape, text, video$"
        ),
    ):
        try:
            exporter.export("p1", tmp_path / "never-noncanonical-kind.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
