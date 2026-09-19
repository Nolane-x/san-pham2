from __future__ import annotations

import json
from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.config import InvalidSceneDuration, normalize_render_config
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class RecordingMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


@pytest.mark.parametrize("field", ["reveal_duration", "hold_duration", "outro_duration"])
def test_render_config_rejects_malformed_present_scene_duration(field):
    with pytest.raises(
        InvalidSceneDuration,
        match=rf"^{field} must be finite$",
    ):
        normalize_render_config({field: "oops"})


def test_render_config_preserves_missing_defaults_and_numeric_strings():
    defaults = normalize_render_config({})
    assert defaults["reveal_duration"] == 8.0
    assert defaults["hold_duration"] == 1.0
    assert defaults["outro_duration"] == 0.3

    numeric = normalize_render_config(
        {
            "reveal_duration": "2.5",
            "hold_duration": "1.25",
            "outro_duration": "0.75",
        }
    )
    assert numeric["reveal_duration"] == 2.5
    assert numeric["hold_duration"] == 1.25
    assert numeric["outro_duration"] == 0.75


def _store_with_later_malformed_duration(
    tmp_path,
    *,
    field: str,
) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Malformed scene duration preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    for scene, fill in ((first, "#FF0000"), (second, "#00AAFF")):
        store.add_visual_object(scene["id"], "shape", payload={"fill": fill})
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.25,
            hold_duration=0.1,
            settings={"style": "color_reveal"},
        )

    with store._connect() as conn:
        if field in {"reveal_duration", "hold_duration"}:
            conn.execute(
                f"UPDATE visual_editor_scenes SET {field}=? WHERE id=?",
                ("oops", second["id"]),
            )
        else:
            row = conn.execute(
                "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
                (second["id"],),
            ).fetchone()
            metadata = json.loads(row["metadata_json"] or "{}")
            render_config = dict(metadata.get("render_config") or {})
            render_config["outro_enabled"] = True
            render_config["outro_duration"] = "oops"
            metadata["render_config"] = render_config
            conn.execute(
                "UPDATE visual_editor_scenes SET metadata_json=? WHERE id=?",
                (
                    json.dumps(metadata, ensure_ascii=False, separators=(",", ":")),
                    second["id"],
                ),
            )

    return store, second["id"]


@pytest.mark.parametrize("field", ["reveal_duration", "hold_duration", "outro_duration"])
def test_project_exporter_rejects_later_malformed_scene_duration_before_any_render(
    tmp_path,
    field,
):
    store, second_scene_id = _store_with_later_malformed_duration(tmp_path, field=field)
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
    output = tmp_path / "project-malformed-duration" / "final.mp4"

    with pytest.raises(
        InvalidSceneDuration,
        match=rf"^scene {second_scene_id} {field} must be finite$",
    ):
        try:
            exporter.export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.parent.exists()
