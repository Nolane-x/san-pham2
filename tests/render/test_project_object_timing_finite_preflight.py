from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.effects import InvalidObjectTiming, ObjectTimingEntry, build_render_timing_plan
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


@pytest.mark.parametrize("field", ["start", "pause", "draw", "push"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_object_timing_entry_rejects_nonfinite_values(field, value):
    values = {"start": 0.0, "pause": 0.25, "draw": 0.5, "push": 0.0}
    values[field] = value

    with pytest.raises(
        ValueError,
        match=rf"^object timing-object timing {field} must be finite$",
    ):
        ObjectTimingEntry("timing-object", **values)


def test_object_timing_entry_accepts_finite_zero_positive_and_large_values():
    entry = ObjectTimingEntry(
        "timing-object",
        start=0.0,
        pause=0.25,
        draw=1e300,
        push=0.0,
    )

    assert entry.object_id == "timing-object"
    assert entry.start == 0.0
    assert entry.pause == 0.25
    assert entry.draw == 1e300
    assert entry.push == 0.0


def test_object_timing_entry_rejects_finite_fields_whose_total_overflows():
    with pytest.raises(
        ValueError,
        match=r"^object timing-object timing total must be finite$",
    ):
        ObjectTimingEntry(
            "timing-object",
            start=0.0,
            pause=1e308,
            draw=1e308,
            push=0.0,
        )


def _store_with_later_nonfinite_timing(
    tmp_path,
    *,
    field: str,
    value: float,
) -> tuple[ProjectStore, str, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Non-finite object timing preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    first_object_id = store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={
            "style": "whiteboard",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": first_object_id, "pause": 0.0, "draw": 0.25, "push": 0.0}
            ],
        },
    )

    second_object_id = store.add_visual_object(
        second["id"],
        "shape",
        name="Second shape",
        payload={"fill": "#00AAFF"},
    )
    custom_timing = {
        "object_id": second_object_id,
        "pause": 0.0,
        "draw": 0.25,
        "push": 0.0,
    }
    custom_timing[field] = value
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={
            "style": "whiteboard",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [custom_timing],
        },
    )
    return store, second["id"], second_object_id


@pytest.mark.parametrize("field", ["pause", "draw", "push"])
@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_project_exporter_rejects_later_nonfinite_custom_timing_before_any_render(
    tmp_path,
    field,
    value,
):
    store, second_scene_id, second_object_id = _store_with_later_nonfinite_timing(
        tmp_path,
        field=field,
        value=value,
    )
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
        match=rf"^scene {second_scene_id} object {second_object_id} timing {field} must be finite$",
    ):
        try:
            exporter.export("p1", tmp_path / "never.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []


@pytest.mark.parametrize("field", ["pause", "draw", "push"])
def test_custom_object_timing_rejects_malformed_present_value(field):
    raw = {"object_id": "object-a", "pause": 0.0, "draw": 0.5, "push": 0.0}
    raw[field] = "oops"

    with pytest.raises(
        InvalidObjectTiming,
        match=rf"^object object-a timing {field} must be finite$",
    ):
        build_render_timing_plan(
            [{"id": "object-a", "visible": True}],
            {
                "object_timing_mode": "custom",
                "reveal_duration": 0.5,
                "custom_object_timing_config": [raw],
            },
        )


def test_custom_object_timing_preserves_numeric_strings():
    plan = build_render_timing_plan(
        [{"id": "object-a", "visible": True}],
        {
            "object_timing_mode": "custom",
            "reveal_duration": 4.0,
            "custom_object_timing_config": [
                {
                    "object_id": "object-a",
                    "pause": "0.25",
                    "draw": "1.5",
                    "push": "0.75",
                }
            ],
        },
    )

    assert [(entry.pause, entry.draw, entry.push) for entry in plan] == [(0.25, 1.5, 0.75)]


@pytest.mark.parametrize("field", ["pause", "draw", "push"])
def test_project_exporter_rejects_later_malformed_custom_timing_before_any_render(
    tmp_path,
    field,
):
    store, second_scene_id, second_object_id = _store_with_later_nonfinite_timing(
        tmp_path,
        field=field,
        value="oops",
    )
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
        InvalidObjectTiming,
        match=rf"^scene {second_scene_id} object {second_object_id} timing {field} must be finite$",
    ):
        try:
            exporter.export("p1", tmp_path / "never-malformed.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []


def test_custom_object_timing_rejects_duplicate_config_for_visible_object():
    with pytest.raises(
        InvalidObjectTiming,
        match=r"^duplicate timing config for object object-a$",
    ):
        build_render_timing_plan(
            [{"id": "object-a", "visible": True}],
            {
                "object_timing_mode": "custom",
                "reveal_duration": 1.0,
                "custom_object_timing_config": [
                    {"object_id": "object-a", "draw": 0.25},
                    {"object_id": "object-a", "draw": 0.75},
                ],
            },
        )


def test_project_exporter_rejects_later_duplicate_visible_object_timing_before_any_render(
    tmp_path,
):
    store = ProjectStore(tmp_path / "duplicate-timing.db")
    store.initialize()
    store.create_project("p1", "Duplicate object timing preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    first_object_id = store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    second_object_id = store.add_visual_object(
        second["id"],
        "shape",
        name="Second shape",
        payload={"fill": "#00AAFF"},
    )
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={
            "style": "whiteboard",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": first_object_id, "draw": 0.25}
            ],
        },
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.25,
        hold_duration=0.1,
        settings={
            "style": "whiteboard",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": second_object_id, "draw": 0.1},
                {"object_id": second_object_id, "draw": 0.2},
            ],
        },
    )

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
        InvalidObjectTiming,
        match=rf"^scene {second['id']} duplicate timing config for object {second_object_id}$",
    ):
        try:
            exporter.export("p1", tmp_path / "never-duplicate.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
