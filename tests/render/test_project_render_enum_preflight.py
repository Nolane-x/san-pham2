from __future__ import annotations

import json
from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.config import InvalidRenderConfig, normalize_render_config
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("visual_mode", "camera-mtoion", "visual_mode must be drawing or camera_motion"),
        ("style", "whitebord", "style must be whiteboard or color_reveal"),
    ],
)
def test_render_config_rejects_unsupported_semantic_enum(field, value, message):
    with pytest.raises(InvalidRenderConfig, match=rf"^{message}$"):
        normalize_render_config({field: value})


@pytest.mark.parametrize(
    ("field", "missing_default", "blank_default"),
    [
        ("visual_mode", "drawing", "drawing"),
        ("style", "whiteboard", "whiteboard"),
    ],
)
def test_render_config_preserves_missing_and_blank_recovered_enum_defaults(
    field,
    missing_default,
    blank_default,
):
    assert normalize_render_config({})[field] == missing_default
    assert normalize_render_config({field: "   "})[field] == blank_default


def _store_with_later_invalid_enum(
    tmp_path,
    *,
    field: str,
    value: str,
) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / f"invalid-{field}.db")
    store.initialize()
    store.create_project("p1", "Semantic enum preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    for scene, fill in ((first, "#FF0000"), (second, "#00AAFF")):
        store.add_visual_object(
            scene["id"],
            "shape",
            payload={"fill": fill},
        )

    store.update_scene_render_settings(
        first["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={"style": "whiteboard", "visual_mode": "drawing"},
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={"style": "whiteboard", "visual_mode": "drawing"},
    )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
            (second["id"],),
        ).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}")
        render_config = dict(metadata.get("render_config") or {})
        render_config[field] = value
        metadata["render_config"] = render_config
        conn.execute(
            "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
            (
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                second["id"],
            ),
        )

    return store, second["id"]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("visual_mode", "camera-mtoion", "visual_mode must be drawing or camera_motion"),
        ("style", "whitebord", "style must be whiteboard or color_reveal"),
    ],
)
def test_project_exporter_rejects_later_invalid_semantic_enum_before_any_render(
    tmp_path,
    field,
    value,
    message,
):
    store, second_scene_id = _store_with_later_invalid_enum(
        tmp_path,
        field=field,
        value=value,
    )
    media = RecordingMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        del output
        render_calls.append(("snapshot", plan.scene_id))
        raise AssertionError("snapshot renderer must not be called")

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
    output = tmp_path / f"never-{field}.mp4"

    with pytest.raises(
        InvalidRenderConfig,
        match=rf"^scene {second_scene_id} {message}$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()
