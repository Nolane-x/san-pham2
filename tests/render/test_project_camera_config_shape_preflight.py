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


def test_render_config_rejects_mapping_custom_camera_config():
    with pytest.raises(
        InvalidRenderConfig,
        match=r"^custom_camera_config must be a list$",
    ):
        normalize_render_config(
            {
                "visual_mode": "camera_motion",
                "custom_camera_enabled": True,
                "custom_camera_config": {
                    "action": "pan_left",
                },
            }
        )


def test_render_config_preserves_valid_custom_camera_list_and_missing_default():
    defaulted = normalize_render_config({"visual_mode": "camera_motion"})
    assert defaulted["custom_camera_config"] == []

    valid = [
        {
            "action": "pan_left",
        }
    ]
    normalized = normalize_render_config(
        {
            "visual_mode": "camera_motion",
            "custom_camera_enabled": True,
            "custom_camera_config": valid,
        }
    )
    assert normalized["custom_camera_config"] == valid


def _store_with_later_mapping_custom_camera_config(
    tmp_path,
) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "camera-config-shape.db")
    store.initialize()
    store.create_project("p1", "Structured camera config preflight")
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
        settings={
            "style": "whiteboard",
            "visual_mode": "drawing",
        },
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={
            "style": "whiteboard",
            "visual_mode": "camera_motion",
            "custom_camera_enabled": True,
            "custom_camera_config": [{"action": "pan_left"}],
        },
    )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
            (second["id"],),
        ).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}")
        render_config = dict(metadata.get("render_config") or {})
        render_config["visual_mode"] = "camera_motion"
        render_config["custom_camera_enabled"] = True
        render_config["custom_camera_config"] = {
            "action": "pan_left",
        }
        metadata["render_config"] = render_config
        conn.execute(
            "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
            (
                json.dumps(
                    metadata,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                second["id"],
            ),
        )

    return store, second["id"]


def test_project_exporter_rejects_later_mapping_custom_camera_before_any_render(
    tmp_path,
):
    store, second_scene_id = _store_with_later_mapping_custom_camera_config(tmp_path)
    media = RecordingMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
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
    output = tmp_path / "never-camera-shape.mp4"

    with pytest.raises(
        InvalidRenderConfig,
        match=rf"^scene {second_scene_id} custom_camera_config must be a list$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()
