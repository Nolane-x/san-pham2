from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render import project_export
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self):
        self.calls = []

    def export(self, clips, output, **kwargs):
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Push contract")
    store.replace_scenes("p1", [Scene(0, "Push")])
    scene = store.list_scenes("p1")[0]
    object_id = store.add_visual_object(
        scene["id"],
        "shape",
        name="Push shape",
        payload={"fill": "#FF0000"},
    )
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "whiteboard"},
    )
    return store, scene, object_id


def _touch_snapshot(plan, output):
    del plan
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(b"png")
    return Path(output)


def _touch_whiteboard(plan, output, **kwargs):
    del plan, kwargs
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).touch()
    return Path(output)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("custom_object_push_config", [{"object_id": "legacy", "direction": "from_left"}]),
        ("large_object_push_mode", "manual"),
        ("large_object_push_enabled", True),
    ],
    ids=["custom-push-config", "non-automatic-mode", "enabled-without-positive-push"],
)
def test_project_exporter_fails_closed_for_unconsumed_large_object_push_controls(
    tmp_path, field, value
):
    error_type = getattr(project_export, "UnsupportedSceneRenderState", RuntimeError)
    store, scene, _object_id = _store(tmp_path)
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "whiteboard", field: value},
    )
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        return _touch_snapshot(plan, output)

    def whiteboard(plan, output, **kwargs):
        render_calls.append(("whiteboard", plan.scene_id))
        return _touch_whiteboard(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(error_type, match=field):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []


def test_project_exporter_accepts_enabled_automatic_push_when_timing_has_positive_push(tmp_path):
    store, scene, object_id = _store(tmp_path)
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={
            "style": "whiteboard",
            "large_object_push_enabled": True,
            "large_object_push_mode": "automatic",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": object_id, "draw": 1.0, "push": 0.25}
            ],
        },
    )
    media = FakeMediaExporter()
    whiteboard_calls = []

    def whiteboard(plan, output, **kwargs):
        whiteboard_calls.append(
            (
                plan.scene_id,
                [entry.push for entry in plan.object_timing],
                kwargs,
            )
        )
        return _touch_whiteboard(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        whiteboard_renderer=whiteboard,
    )

    result = exporter.export("p1", tmp_path / "push.mp4")

    assert result == tmp_path / "push.mp4"
    assert whiteboard_calls == [
        (scene["id"], [0.25], {"width": 1280, "height": 720, "fps": 24})
    ]
    assert len(media.calls) == 1


def test_project_exporter_rejects_positive_push_when_large_object_push_is_disabled(tmp_path):
    store, scene, object_id = _store(tmp_path)
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={
            "style": "whiteboard",
            "large_object_push_enabled": False,
            "large_object_push_mode": "automatic",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": object_id, "draw": 1.0, "push": 0.25}
            ],
        },
    )
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        return _touch_snapshot(plan, output)

    def whiteboard(plan, output, **kwargs):
        render_calls.append(("whiteboard", plan.scene_id))
        return _touch_whiteboard(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(
        project_export.UnsupportedSceneRenderState,
        match="large_object_push_enabled",
    ):
        try:
            exporter.export("p1", tmp_path / "never-disabled-push.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
