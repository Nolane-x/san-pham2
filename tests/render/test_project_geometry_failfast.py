from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        raise AssertionError("media exporter must not execute before project geometry preflight")


def _project_store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Project geometry fail-fast")
    store.replace_scenes("p1", [Scene(0, "Only scene")])
    scene = store.list_scenes("p1")[0]
    store.add_visual_object(
        scene["id"],
        "shape",
        name="Shape",
        payload={"fill": "#FF0000"},
    )
    return store


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", float("inf"), "width must be finite"),
        ("height", float("-inf"), "height must be finite"),
        ("fps", float("nan"), "fps must be finite"),
    ],
)
def test_project_exporter_rejects_nonfinite_geometry_before_any_side_effect(
    tmp_path,
    field,
    value,
    message,
):
    store = _project_store(tmp_path)
    media = RecordingMediaExporter()
    snapshot_calls: list[tuple] = []

    def snapshot_renderer(plan, output):
        snapshot_calls.append((plan.scene_id, Path(output)))
        raise AssertionError("snapshot renderer must not execute before project geometry preflight")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot_renderer,
    )
    output = tmp_path / "project-output" / "final.mp4"
    geometry = {"width": 1280, "height": 720, "fps": 24}
    geometry[field] = value

    with pytest.raises(ValueError, match=rf"^{message}$"):
        exporter.export("p1", output, **geometry)

    assert snapshot_calls == []
    assert media.calls == []
    assert not output.parent.exists()


@pytest.mark.parametrize("fps", [0, -1, 0.5])
def test_project_exporter_rejects_subunit_fps_before_any_side_effect(tmp_path, fps):
    store = _project_store(tmp_path)
    media = RecordingMediaExporter()
    snapshot_calls: list[tuple] = []

    def snapshot_renderer(plan, output):
        snapshot_calls.append((plan.scene_id, Path(output)))
        raise AssertionError("snapshot renderer must not execute before project geometry preflight")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot_renderer,
    )
    output = tmp_path / "project-output" / "final.mp4"

    with pytest.raises(ValueError, match=r"^fps must be >= 1$"):
        exporter.export("p1", output, fps=fps)

    assert snapshot_calls == []
    assert media.calls == []
    assert not output.parent.exists()
