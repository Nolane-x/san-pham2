from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render import project_export
from nolane_studio.render.compositor import CompositionRequiresVideo
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
    store.add_visual_object(second["id"], "video", name="Video", source="clip.mp4")
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
    store.add_visual_object(first["id"], "video", name="Video", source="clip.mp4")
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
    store.add_visual_object(second["id"], "video", name="Video", source="clip.mp4")
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


def test_project_exporter_rejects_project_without_scenes(tmp_path):
    store = ProjectStore(tmp_path / "empty.db")
    store.initialize()
    store.create_project("empty", "Empty")
    exporter = ProjectSceneExporter(store, media_exporter=FakeMediaExporter())

    with pytest.raises(ValueError, match="scene"):
        exporter.export("empty", tmp_path / "never.mp4")
