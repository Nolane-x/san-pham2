from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render import project_export
from nolane_studio.render.exporter import (
    build_image_segment_command,
    build_video_segment_command,
)
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls = []

    def export(self, clips, output, **kwargs):
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _voice_store(tmp_path: Path, *, existing_voice: bool = True):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Narration export")
    store.replace_scenes("p1", [Scene(0, "Narrated scene")])
    scene = store.list_scenes("p1")[0]
    store.add_visual_object(
        scene["id"],
        "shape",
        name="Shape",
        payload={"fill": "#3366FF"},
    )
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=0.25,
        hold_duration=0.25,
        settings={"style": "whiteboard"},
    )
    voice = tmp_path / "voice.mp3"
    if existing_voice:
        voice.write_bytes(b"fake-mp3")
    metadata = dict(scene["metadata"])
    metadata.update(
        {
            "voice_media_id": f"voice-{scene['id']}",
            "voice_path": str(voice),
        }
    )
    store.update_scene(scene["id"], metadata=metadata)
    return store, scene, voice


def _touch_whiteboard(plan, output, **kwargs):
    del plan, kwargs
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).touch()
    return Path(output)


def test_project_export_binds_persisted_scene_voice_to_scene_clip(tmp_path):
    store, scene, voice = _voice_store(tmp_path)
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        whiteboard_renderer=_touch_whiteboard,
    )

    exporter.export("p1", tmp_path / "final.mp4")

    assert len(media.calls) == 1
    clips = media.calls[0][0]
    assert len(clips) == 1
    assert clips[0].clip_id == scene["id"]
    assert clips[0].narration_audio == str(voice)


def test_project_export_preflights_missing_persisted_scene_voice_before_render(tmp_path):
    error_type = getattr(project_export, "MissingSceneNarration", None)
    assert error_type is not None, "project export needs an explicit missing-narration boundary"

    store, scene, voice = _voice_store(tmp_path, existing_voice=False)
    media = FakeMediaExporter()
    render_calls = []

    def whiteboard(plan, output, **kwargs):
        del output, kwargs
        render_calls.append(plan.scene_id)
        return tmp_path / "should-not-exist.mp4"

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(error_type) as exc_info:
        exporter.export("p1", tmp_path / "never.mp4")

    message = str(exc_info.value)
    assert scene["id"] in message
    assert str(voice) in message
    assert render_calls == []
    assert media.calls == []


def test_image_segment_command_pads_and_trims_scene_narration():
    command = build_image_segment_command(
        "ffmpeg",
        "scene.png",
        "segment.mp4",
        duration=2.5,
        narration_audio="voice.mp3",
    )

    joined = " ".join(command)
    assert "voice.mp3" in command
    assert "apad" in joined
    assert "atrim=duration=2.500000" in joined
    assert "[narration]" in joined


def test_video_segment_command_mixes_scene_narration_with_source_audio():
    command = build_video_segment_command(
        "ffmpeg",
        "scene.mp4",
        "segment.mp4",
        has_audio=True,
        duration=3.0,
        narration_audio="voice.mp3",
    )

    joined = " ".join(command)
    assert "voice.mp3" in command
    assert "amix=inputs=2" in joined
    assert "atrim=duration=3.000000" in joined
    assert "[mixeda]" in joined


def test_video_segment_command_uses_scene_narration_when_source_is_silent():
    command = build_video_segment_command(
        "ffmpeg",
        "scene.mp4",
        "segment.mp4",
        has_audio=False,
        duration=3.0,
        narration_audio="voice.mp3",
    )

    joined = " ".join(command)
    assert "voice.mp3" in command
    assert "amix=inputs=2" not in joined
    assert "atrim=duration=3.000000" in joined
    assert "[narration]" in joined
