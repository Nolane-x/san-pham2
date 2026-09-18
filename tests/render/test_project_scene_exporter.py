from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render import project_export
from nolane_studio.render.compositor import CompositionError, CompositionRequiresVideo
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.whiteboard_compositor import UnsupportedWhiteboardMotion
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self):
        self.calls = []

    def export(self, clips, output, **kwargs):
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs, [Path(clip.path).exists() for clip in clips]))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Project export")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")
    store.add_visual_object(first["id"], "shape", name="First shape", payload={"fill": "#FF0000"})
    store.add_visual_object(second["id"], "text", name="Second text", payload={"text": "Second"})
    store.update_scene_render_settings(
        first["id"], reveal_duration=2.0, hold_duration=1.0, settings={"style": "whiteboard"}
    )
    store.update_scene_render_settings(
        second["id"], reveal_duration=1.5, hold_duration=2.5, settings={"style": "color_reveal"}
    )
    return store, first, second


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


def _touch_source(tmp_path, name="clip.mp4"):
    source = tmp_path / name
    source.touch()
    return str(source)


def test_project_exporter_routes_whiteboard_before_snapshot_and_keeps_workspace_alive(tmp_path):
    store, first, second = _store(tmp_path)
    media = FakeMediaExporter()
    snapshots = []
    whiteboards = []

    def snapshot(plan, output):
        snapshots.append(plan.scene_id)
        Path(output).write_bytes(b"png")
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        whiteboards.append((plan.scene_id, kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )
    output = tmp_path / "final.mp4"

    result = exporter.export("p1", output)

    assert result == output
    assert snapshots == [second["id"]]
    assert whiteboards == [(first["id"], {"width": 1280, "height": 720, "fps": 24})]
    assert len(media.calls) == 1
    clips, called_output, kwargs, existed_during_call = media.calls[0]
    assert called_output == output
    assert existed_during_call == [True, True]
    assert [clip.clip_id for clip in clips] == [first["id"], second["id"]]
    assert [clip.kind for clip in clips] == ["video", "image"]
    assert [clip.duration for clip in clips] == [3.0, 4.0]
    assert clips[0].trim_end == clips[0].duration
    assert clips[0].render_profile is None
    assert clips[1].render_profile["style"] == "color_reveal"
    assert kwargs == {"width": 1280, "height": 720, "fps": 24}
    assert all(not Path(clip.path).exists() for clip in clips)


def test_project_exporter_applies_exact_persisted_media_order(tmp_path):
    store, first, second = _store(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [second["id"], first["id"]],
        },
    )
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        whiteboard_renderer=_touch_whiteboard,
    )

    exporter.export("p1", tmp_path / "ordered.mp4")

    assert len(media.calls) == 1
    clips = media.calls[0][0]
    assert [clip.clip_id for clip in clips] == [second["id"], first["id"]]


@pytest.mark.parametrize(
    "order_builder",
    [
        lambda first, second: [first["id"]],
        lambda first, second: [first["id"], first["id"]],
        lambda first, second: [first["id"], "missing-scene"],
    ],
    ids=["incomplete", "duplicate", "unknown"],
)
def test_project_exporter_fails_closed_for_ambiguous_media_order(tmp_path, order_builder):
    error_type = getattr(project_export, "UnsupportedProjectTimeline", None)
    assert error_type is not None, "project export needs an explicit unsupported-timeline boundary"

    store, first, second = _store(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": order_builder(first, second),
        },
    )
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        whiteboard_renderer=_touch_whiteboard,
    )

    with pytest.raises(error_type, match="mediaOrder"):
        exporter.export("p1", tmp_path / "never.mp4")
    assert media.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("clips", {"legacy": {"start": 0.0}}),
        ("videoClips", [{"legacy": "video"}]),
        ("audioClips", [{"legacy": "audio"}]),
    ],
)
def test_project_exporter_fails_closed_for_unrecovered_track_payloads(tmp_path, field, value):
    error_type = getattr(project_export, "UnsupportedProjectTimeline", None)
    assert error_type is not None, "project export needs an explicit unsupported-timeline boundary"

    store, first, second = _store(tmp_path)
    state = {"clips": {}, "videoClips": [], "audioClips": [], "mediaOrder": []}
    state[field] = value
    store.save_timeline("p1", state)
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        whiteboard_renderer=_touch_whiteboard,
    )

    with pytest.raises(error_type, match=field):
        exporter.export("p1", tmp_path / "never.mp4")
    assert media.calls == []


def test_project_exporter_propagates_video_compositor_refusal(tmp_path):
    store, _first, second = _store(tmp_path)
    store.add_visual_object(
        second["id"], "video", name="Video", source=_touch_source(tmp_path, "refusal.mp4")
    )
    media = FakeMediaExporter()

    def video_renderer(plan, output, **kwargs):
        raise CompositionRequiresVideo("video path refused")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        video_renderer=video_renderer,
        whiteboard_renderer=_touch_whiteboard,
    )

    with pytest.raises(CompositionRequiresVideo, match="refused"):
        exporter.export("p1", tmp_path / "never.mp4")
    assert media.calls == []


def test_project_exporter_fails_closed_before_video_renderer_for_whiteboard_source_video(tmp_path):
    store, first, _second = _store(tmp_path)
    store.add_visual_object(
        first["id"], "video", name="Video", source=_touch_source(tmp_path, "whiteboard.mp4")
    )
    media = FakeMediaExporter()
    video_calls = []

    def video_renderer(plan, output, **kwargs):
        video_calls.append((plan.scene_id, kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        video_renderer=video_renderer,
        whiteboard_renderer=_touch_whiteboard,
    )

    with pytest.raises(UnsupportedWhiteboardMotion, match="source-video"):
        exporter.export("p1", tmp_path / "never.mp4")

    assert video_calls == []
    assert media.calls == []


def test_project_exporter_keeps_color_reveal_source_video_on_video_renderer(tmp_path):
    store, _first, second = _store(tmp_path)
    store.add_visual_object(
        second["id"], "video", name="Video", source=_touch_source(tmp_path, "color.mp4")
    )
    media = FakeMediaExporter()
    video_calls = []

    def video_renderer(plan, output, **kwargs):
        video_calls.append((plan.scene_id, kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
        video_renderer=video_renderer,
        whiteboard_renderer=_touch_whiteboard,
    )

    exporter.export("p1", tmp_path / "color-video.mp4")

    assert video_calls == [(second["id"], {"width": 1280, "height": 720, "fps": 24})]
    clips = media.calls[0][0]
    assert [clip.clip_id for clip in clips] == [store.list_scenes("p1")[0]["id"], second["id"]]
    assert [clip.kind for clip in clips] == ["video", "video"]


@pytest.mark.parametrize(
    ("kind", "suffix"),
    [("image", ".png"), ("video", ".mp4")],
    ids=["missing-image", "missing-video"],
)
def test_project_exporter_preflights_all_scene_media_before_render(tmp_path, kind, suffix):
    error_type = getattr(project_export, "MissingSceneMedia", RuntimeError)
    store, _first, second = _store(tmp_path)
    missing = tmp_path / f"missing{suffix}"
    object_id = store.add_visual_object(
        second["id"], kind, name=f"Missing {kind}", source=str(missing)
    )
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        return _touch_snapshot(plan, output)

    def whiteboard(plan, output, **kwargs):
        render_calls.append(("whiteboard", plan.scene_id))
        return _touch_whiteboard(plan, output, **kwargs)

    def video(plan, output, **kwargs):
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(error_type) as exc_info:
        exporter.export("p1", tmp_path / "never.mp4")

    message = str(exc_info.value)
    assert second["id"] in message
    assert object_id in message
    assert str(missing) in message
    assert render_calls == []
    assert media.calls == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("remove_background_enabled", True),
        ("auto_object_fx_enabled", True),
        ("custom_object_effect_config", [{"effect": "legacy-effect"}]),
        ("custom_object_sound_config", [{"sound": "legacy-sound"}]),
        ("custom_draw_points", [[0.0, 0.0], [1.0, 1.0]]),
    ],
    ids=[
        "remove-background",
        "auto-object-fx",
        "custom-object-effect",
        "custom-object-sound",
        "custom-draw-points",
    ],
)
def test_project_exporter_fails_closed_before_render_for_unsupported_persisted_render_state(
    tmp_path, field, value
):
    error_type = getattr(project_export, "UnsupportedSceneRenderState", RuntimeError)
    store, first, _second = _store(tmp_path)
    store.update_scene_render_settings(first["id"], settings={field: value})
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        return _touch_snapshot(plan, output)

    def whiteboard(plan, output, **kwargs):
        render_calls.append(("whiteboard", plan.scene_id))
        return _touch_whiteboard(plan, output, **kwargs)

    def video(plan, output, **kwargs):
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(error_type, match=field):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []


def test_project_exporter_rejects_project_without_scenes(tmp_path):
    store = ProjectStore(tmp_path / "empty.db")
    store.initialize()
    store.create_project("empty", "Empty")
    exporter = ProjectSceneExporter(store, media_exporter=FakeMediaExporter())

    with pytest.raises(ValueError, match="scene"):
        exporter.export("empty", tmp_path / "never.mp4")


def _store_with_later_corrupt_image(tmp_path):
    store, first, second = _store(tmp_path)
    corrupt = tmp_path / "corrupt-image.png"
    corrupt.write_bytes(b"this is not a decodable image")
    object_id = store.add_visual_object(
        second["id"],
        "image",
        name="Corrupt image",
        source=str(corrupt),
    )
    return store, first, second, object_id, corrupt


def test_project_media_preflight_rejects_existing_undecodable_image(tmp_path):
    store, _first, second, object_id, corrupt = _store_with_later_corrupt_image(tmp_path)
    plans = project_export.build_scene_render_plan(store, "p1")

    with pytest.raises(
        CompositionError,
        match=(
            rf"^scene {second['id']} object {object_id} "
            rf"unable to decode scene image: {corrupt}$"
        ),
    ):
        project_export.validate_project_scene_media(plans)


def test_project_exporter_rejects_later_undecodable_image_before_any_render(tmp_path):
    store, _first, second, object_id, corrupt = _store_with_later_corrupt_image(tmp_path)
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        return project_export.render_scene_snapshot(plan, output)

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
        CompositionError,
        match=(
            rf"^scene {second['id']} object {object_id} "
            rf"unable to decode scene image: {corrupt}$"
        ),
    ):
        try:
            exporter.export("p1", tmp_path / "never-corrupt-image.mp4")
        finally:
            assert render_calls == []
            assert media.calls == []
