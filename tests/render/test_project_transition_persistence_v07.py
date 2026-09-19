from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene, TransitionSpec
from nolane_studio.render.project_export import ProjectSceneExporter, UnsupportedProjectTimeline
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _touch_snapshot(plan, output):
    del plan
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_bytes(b"png")
    return Path(output)


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Transitions")
    store.replace_scenes(
        "p1",
        [Scene(0, "First"), Scene(1, "Second"), Scene(2, "Third")],
    )
    scenes = store.list_scenes("p1")
    for scene in scenes:
        store.add_visual_object(
            scene["id"],
            "shape",
            name="Card",
            payload={"fill": "#ffffff"},
        )
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=0.5,
            hold_duration=0.5,
            settings={"style": "color_reveal"},
        )
    return store, scenes


def test_project_export_routes_persisted_additive_transitions_to_media_exporter(tmp_path):
    store, scenes = _store(tmp_path)
    first, second, third = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"], second["id"], third["id"]],
            "transitions": [
                {
                    "from_id": first["id"],
                    "to_id": second["id"],
                    "effect": "wipeleft",
                    "duration": 0.6,
                },
                {
                    "from_id": second["id"],
                    "to_id": third["id"],
                    "effect": "fade",
                    "duration": 0.4,
                },
            ],
        },
    )
    media = FakeMediaExporter()

    ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=_touch_snapshot,
    ).export("p1", tmp_path / "final.mp4")

    assert len(media.calls) == 1
    clips, _output, kwargs = media.calls[0]
    assert [clip.clip_id for clip in clips] == [
        first["id"],
        second["id"],
        third["id"],
    ]
    assert kwargs["transitions"] == [
        TransitionSpec(first["id"], second["id"], "wipeleft", 0.6),
        TransitionSpec(second["id"], third["id"], "fade", 0.4),
    ]


def test_project_export_preflights_transition_adjacency_before_render(tmp_path):
    store, scenes = _store(tmp_path)
    first, second, third = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"], second["id"], third["id"]],
            "transitions": [
                {
                    "from_id": first["id"],
                    "to_id": third["id"],
                    "effect": "fade",
                    "duration": 0.5,
                }
            ],
        },
    )
    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(plan.scene_id)
        return _touch_snapshot(plan, output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
    )

    with pytest.raises(UnsupportedProjectTimeline, match="adjacent"):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []
