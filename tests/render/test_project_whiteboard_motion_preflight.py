from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.whiteboard_compositor import (
    UnsupportedWhiteboardMotion,
    WhiteboardSceneCompositor,
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
    def run(self, command, *, timeout=None):
        del timeout
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def _layer_renderer(plan, output, *, objects, transparent, width, height):
    del plan, objects, transparent, width, height
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def _store_with_later_motion_case(tmp_path, case: str) -> tuple[ProjectStore, str, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Whiteboard motion preflight")
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
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={"style": "whiteboard"},
    )

    second_object_id = store.add_visual_object(
        second["id"],
        "shape",
        name="Second shape",
        payload={"fill": "#00AAFF"},
    )
    settings: dict[str, object] = {"style": "whiteboard"}
    if case == "brush":
        settings["brush_mode"] = "diagonal"
    elif case == "push":
        settings.update(
            {
                "large_object_push_enabled": True,
                "large_object_push_direction": "from_right",
                "object_timing_mode": "custom",
                "custom_object_timing_config": [
                    {"object_id": second_object_id, "draw": 0.25, "push": 0.2}
                ],
            }
        )
    elif case == "outro":
        settings.update(
            {
                "outro_enabled": True,
                "outro_direction": "right",
                "outro_duration": 0.2,
            }
        )
    else:  # pragma: no cover - test parametrization owns the cases
        raise AssertionError(case)

    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings=settings,
    )
    return store, first["id"], second["id"]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("brush", "brush mode"),
        ("push", "push direction"),
        ("outro", "outro direction"),
    ],
)
def test_project_exporter_preflights_later_unsupported_whiteboard_motion_before_any_render(
    tmp_path, case, message
):
    store, _first_scene_id, _second_scene_id = _store_with_later_motion_case(tmp_path, case)
    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []
    compositor = WhiteboardSceneCompositor(
        ffmpeg="ffmpeg",
        runner=FakeRunner(),
        layer_renderer=_layer_renderer,
    )

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def whiteboard(plan, output, **kwargs):
        render_calls.append(("whiteboard", plan.scene_id))
        return compositor.render(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(UnsupportedWhiteboardMotion, match=message):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []
