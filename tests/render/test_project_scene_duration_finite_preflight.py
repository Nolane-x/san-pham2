from __future__ import annotations

import json
from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.config import normalize_render_config
from nolane_studio.render.effects import (
    ObjectTimingEntry,
    RenderProfile,
    estimate_object_timeline_seconds,
)
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


@pytest.mark.parametrize("field", ["reveal_duration", "hold_duration"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_render_profile_rejects_nonfinite_durations(field, value):
    values = {"reveal_duration": 0.5, "hold_duration": 1.0}
    values[field] = value

    with pytest.raises(
        ValueError,
        match=rf"^render profile {field} must be finite$",
    ):
        RenderProfile(**values)


def test_render_profile_rejects_finite_fields_whose_total_overflows():
    with pytest.raises(
        ValueError,
        match=r"^render profile total duration must be finite$",
    ):
        RenderProfile(reveal_duration=1e308, hold_duration=1e308)


@pytest.mark.parametrize("field", ["reveal_duration", "hold_duration", "outro_duration"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_render_config_rejects_nonfinite_scene_durations(field, value):
    with pytest.raises(
        ValueError,
        match=rf"^{field} must be finite$",
    ):
        normalize_render_config({field: value})


def test_render_config_preserves_existing_finite_duration_bounds():
    config = normalize_render_config(
        {
            "reveal_duration": -3.0,
            "hold_duration": 9999.0,
            "outro_duration": 99.0,
        }
    )

    assert config["reveal_duration"] == 0.0
    assert config["hold_duration"] == 3600.0
    assert config["outro_duration"] == 5.0


@pytest.mark.parametrize(
    "field,kwargs",
    [
        ("hold_duration", {"hold_duration": float("inf"), "outro_duration": 0.0}),
        ("outro_duration", {"hold_duration": 0.0, "outro_duration": float("inf")}),
    ],
)
def test_object_timeline_estimate_rejects_nonfinite_scene_duration_components(field, kwargs):
    plan = [ObjectTimingEntry("object-a", start=0.0, pause=0.0, draw=0.5, push=0.0)]

    with pytest.raises(
        ValueError,
        match=rf"^{field} must be finite$",
    ):
        estimate_object_timeline_seconds(plan, **kwargs)


def test_object_timeline_estimate_rejects_total_overflow():
    plan = [ObjectTimingEntry("object-a", start=0.0, pause=0.0, draw=1e308, push=0.0)]

    with pytest.raises(
        ValueError,
        match=r"^scene timeline total duration must be finite$",
    ):
        estimate_object_timeline_seconds(
            plan,
            hold_duration=1e308,
            outro_duration=0.0,
        )


def _store_with_later_corrupt_duration(
    tmp_path,
    *,
    field: str,
) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Finite scene duration preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(first["id"], "shape", payload={"fill": "#FF0000"})
    store.add_visual_object(second["id"], "shape", payload={"fill": "#00AAFF"})
    for scene in (first, second):
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
                (float("inf"), second["id"]),
            )
        else:
            row = conn.execute(
                "SELECT metadata_json FROM visual_editor_scenes WHERE id=?",
                (second["id"],),
            ).fetchone()
            metadata = json.loads(row["metadata_json"] or "{}")
            render_config = dict(metadata.get("render_config") or {})
            render_config["outro_enabled"] = True
            render_config["outro_duration"] = float("inf")
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
def test_project_exporter_rejects_later_corrupt_scene_duration_before_any_render(
    tmp_path,
    field,
):
    store, second_scene_id = _store_with_later_corrupt_duration(tmp_path, field=field)
    media = FakeMediaExporter()
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

    with pytest.raises(
        ValueError,
        match=rf"^scene {second_scene_id} {field} must be finite$",
    ):
        try:
            exporter.export("p1", tmp_path / "never.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
