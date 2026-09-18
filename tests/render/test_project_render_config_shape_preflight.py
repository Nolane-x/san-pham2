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


def test_render_config_rejects_mapping_custom_object_timing_config():
    with pytest.raises(
        ValueError,
        match=r"^custom_object_timing_config must be a list$",
    ):
        normalize_render_config(
            {
                "object_timing_mode": "custom",
                "custom_object_timing_config": {
                    "object_id": "object-a",
                    "draw": 0.5,
                },
            }
        )


def test_render_config_preserves_valid_custom_timing_list_and_missing_default():
    defaulted = normalize_render_config({"object_timing_mode": "custom"})
    assert defaulted["custom_object_timing_config"] == []

    valid = [
        {
            "object_id": "object-a",
            "pause": "0.25",
            "draw": "0.5",
            "push": "0.0",
        }
    ]
    normalized = normalize_render_config(
        {
            "object_timing_mode": "custom",
            "custom_object_timing_config": valid,
        }
    )
    assert normalized["custom_object_timing_config"] == valid


def _store_with_later_mapping_custom_timing(tmp_path) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Structured timing shape preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    for scene, fill in ((first, "#FF0000"), (second, "#00AAFF")):
        object_id = store.add_visual_object(
            scene["id"],
            "shape",
            payload={"fill": fill},
        )
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.25,
            hold_duration=0.1,
            settings={
                "style": "whiteboard",
                "object_timing_mode": "custom",
                "custom_object_timing_config": [
                    {"object_id": object_id, "draw": 0.25}
                ],
            },
        )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
            (second["id"],),
        ).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}")
        render_config = dict(metadata.get("render_config") or {})
        render_config["object_timing_mode"] = "custom"
        render_config["custom_object_timing_config"] = {
            "object_id": "persisted-corrupt-entry",
            "draw": 0.75,
        }
        metadata["render_config"] = render_config
        conn.execute(
            "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
            (
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                second["id"],
            ),
        )

    return store, second["id"]


def test_project_exporter_rejects_later_mapping_custom_timing_before_any_render(
    tmp_path,
):
    store, second_scene_id = _store_with_later_mapping_custom_timing(tmp_path)
    media = RecordingMediaExporter()
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
    output = tmp_path / "never-structured-config.mp4"

    with pytest.raises(
        ValueError,
        match=rf"^scene {second_scene_id} custom_object_timing_config must be a list$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()


def test_render_config_rejects_sequence_coerced_top_level_shape():
    with pytest.raises(
        InvalidRenderConfig,
        match=r"^render_config must be a mapping$",
    ):
        normalize_render_config(
            [
                ["style", "whiteboard"],
                ["visual_mode", "drawing"],
            ]
        )


def test_project_exporter_rejects_later_sequence_top_level_render_config_before_any_render(
    tmp_path,
):
    store = ProjectStore(tmp_path / "top-level-render-config-shape.db")
    store.initialize()
    store.create_project("p1", "Top-level render config preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    for scene, fill in ((first, "#FF0000"), (second, "#00AAFF")):
        store.add_visual_object(
            scene["id"],
            "shape",
            payload={"fill": fill},
        )
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.25,
            hold_duration=0.1,
            settings={
                "style": "whiteboard",
                "visual_mode": "drawing",
            },
        )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
            (second["id"],),
        ).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}")
        metadata["render_config"] = [
            ["style", "whiteboard"],
            ["visual_mode", "drawing"],
        ]
        conn.execute(
            "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
            (
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                second["id"],
            ),
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
    output = tmp_path / "never-top-level-render-config.mp4"

    with pytest.raises(
        InvalidRenderConfig,
        match=rf"^scene {second['id']} render_config must be a mapping$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()



def test_render_config_rejects_sequence_coerced_auto_object_fx_config():
    with pytest.raises(
        InvalidRenderConfig,
        match=r"^auto_object_fx_config must be a mapping$",
    ):
        normalize_render_config(
            {
                "auto_object_fx_enabled": False,
                "auto_object_fx_config": [["mode", "wiggle"]],
            }
        )


def test_project_exporter_rejects_later_sequence_auto_object_fx_config_before_any_render(
    tmp_path,
):
    store = ProjectStore(tmp_path / "auto-object-fx-shape.db")
    store.initialize()
    store.create_project("p1", "Auto object FX shape preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    for scene, fill in ((first, "#FF0000"), (second, "#00AAFF")):
        store.add_visual_object(
            scene["id"],
            "shape",
            payload={"fill": fill},
        )
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.25,
            hold_duration=0.1,
            settings={
                "style": "whiteboard",
                "auto_object_fx_enabled": False,
            },
        )

    with store._connect() as conn:
        row = conn.execute(
            "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
            (second["id"],),
        ).fetchone()
        metadata = json.loads(row["metadata_json"] or "{}")
        render_config = dict(metadata.get("render_config") or {})
        render_config["auto_object_fx_enabled"] = False
        render_config["auto_object_fx_config"] = [["mode", "wiggle"]]
        metadata["render_config"] = render_config
        conn.execute(
            "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
            (
                json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                second["id"],
            ),
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
    output = tmp_path / "never-auto-object-fx-shape.mp4"

    with pytest.raises(
        InvalidRenderConfig,
        match=rf"^scene {second['id']} auto_object_fx_config must be a mapping$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()
