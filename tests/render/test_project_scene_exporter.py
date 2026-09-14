from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.compositor import CompositionRequiresVideo
from nolane_studio.render.project_export import ProjectSceneExporter
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


def test_project_exporter_composes_scenes_in_persisted_order_and_keeps_workspace_alive(tmp_path):
    store, first, second = _store(tmp_path)
    media = FakeMediaExporter()
    rendered = []

    def snapshot(plan, output):
        rendered.append(plan.scene_id)
        Path(output).write_bytes(b"png")
        return Path(output)

    exporter = ProjectSceneExporter(store, media_exporter=media, snapshot_renderer=snapshot)
    output = tmp_path / "final.mp4"

    result = exporter.export("p1", output)

    assert result == output
    assert rendered == [first["id"], second["id"]]
    assert len(media.calls) == 1
    clips, called_output, kwargs, existed_during_call = media.calls[0]
    assert called_output == output
    assert existed_during_call == [True, True]
    assert [clip.clip_id for clip in clips] == [first["id"], second["id"]]
    assert [clip.duration for clip in clips] == [3.0, 4.0]
    assert [clip.render_profile["style"] for clip in clips] == ["whiteboard", "color_reveal"]
    assert kwargs == {"width": 1280, "height": 720, "fps": 24}
    assert all(not Path(clip.path).exists() for clip in clips)


def test_project_exporter_propagates_video_compositor_refusal(tmp_path):
    store, first, _second = _store(tmp_path)
    store.add_visual_object(first["id"], "video", name="Video", source="clip.mp4")
    media = FakeMediaExporter()

    def video_renderer(plan, output, **kwargs):
        raise CompositionRequiresVideo("video path refused")

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        video_renderer=video_renderer,
    )

    with pytest.raises(CompositionRequiresVideo, match="refused"):
        exporter.export("p1", tmp_path / "never.mp4")
    assert media.calls == []


def test_project_exporter_rejects_project_without_scenes(tmp_path):
    store = ProjectStore(tmp_path / "empty.db")
    store.initialize()
    store.create_project("empty", "Empty")
    exporter = ProjectSceneExporter(store, media_exporter=FakeMediaExporter())

    with pytest.raises(ValueError, match="scene"):
        exporter.export("empty", tmp_path / "never.mp4")
