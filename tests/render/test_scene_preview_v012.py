from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
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


def _store(tmp_path: Path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Preview")
    store.replace_scenes(
        "p1",
        [
            Scene(0, "First scene"),
            Scene(1, "Second scene"),
        ],
    )
    scenes = store.list_scenes("p1")
    for scene in scenes:
        store.add_visual_object(
            scene["id"],
            "shape",
            name=f"Shape {scene['id']}",
            payload={"fill": "#3366FF"},
        )
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.4,
            hold_duration=0.6,
            settings={"style": "whiteboard"},
        )
    return store, scenes


def _whiteboard_recorder(calls):
    def render(plan, output, **kwargs):
        calls.append((plan.scene_id, kwargs))
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    return render


def test_selected_scene_preview_renders_only_selected_scene_and_keeps_narration(tmp_path):
    store, scenes = _store(tmp_path)
    selected, other = scenes
    voice = tmp_path / "selected.wav"
    voice.write_bytes(b"voice")
    metadata = dict(selected["metadata"])
    metadata.update(
        {
            "voice_media_id": f"voice-{selected['id']}",
            "voice_path": str(voice),
        }
    )
    store.update_scene(selected["id"], metadata=metadata)

    # Deliberately leave a render state on the other scene that project export
    # cannot render yet. Selected-scene preview must not render/preflight it.
    store.update_scene_render_settings(
        other["id"],
        reveal_duration=0.4,
        hold_duration=0.6,
        settings={"style": "whiteboard", "hand_style": "hand-2.png"},
    )

    render_calls = []
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        whiteboard_renderer=_whiteboard_recorder(render_calls),
    )

    output = exporter.preview_scene(
        "p1",
        selected["id"],
        tmp_path / "preview.mp4",
    )

    assert output == tmp_path / "preview.mp4"
    assert [scene_id for scene_id, _kwargs in render_calls] == [selected["id"]]
    assert len(media.calls) == 1
    clips, _output, kwargs = media.calls[0]
    assert len(clips) == 1
    assert clips[0].clip_id == selected["id"]
    assert clips[0].narration_audio == str(voice)
    assert "transitions" not in kwargs


def test_selected_scene_preview_applies_scene_trim_speed_without_transition(tmp_path):
    store, scenes = _store(tmp_path)
    selected, other = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [other["id"], selected["id"]],
            "sceneEdits": [
                {
                    "scene_id": selected["id"],
                    "trim_start": 0.1,
                    "trim_end": 0.9,
                    "speed": 2.0,
                },
                {
                    "scene_id": other["id"],
                    "trim_start": 0.0,
                    "trim_end": 1.0,
                    "speed": 1.0,
                },
            ],
            "transitions": [
                {
                    "from_id": other["id"],
                    "to_id": selected["id"],
                    "effect": "fade",
                    "duration": 0.2,
                }
            ],
        },
    )

    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        whiteboard_renderer=_whiteboard_recorder([]),
    )

    exporter.preview_scene(
        "p1",
        selected["id"],
        tmp_path / "edited-preview.mp4",
    )

    clips, _output, kwargs = media.calls[0]
    assert len(clips) == 1
    clip = clips[0]
    assert clip.clip_id == selected["id"]
    assert clip.trim_start == pytest.approx(0.1)
    assert clip.trim_end == pytest.approx(0.9)
    assert clip.speed == pytest.approx(2.0)
    assert clip.duration == pytest.approx(0.4)
    assert "transitions" not in kwargs


def test_selected_scene_preview_rejects_unknown_scene_before_render(tmp_path):
    store, _scenes = _store(tmp_path)
    render_calls = []
    media = FakeMediaExporter()
    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        whiteboard_renderer=_whiteboard_recorder(render_calls),
    )

    with pytest.raises(KeyError):
        exporter.preview_scene("p1", "missing-scene", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []
