from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter, UnsupportedProjectTimeline
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self):
        self.calls = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Timeline preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")
    store.add_visual_object(first["id"], "shape", name="First shape", payload={"fill": "#FF0000"})
    store.add_visual_object(second["id"], "text", name="Second text", payload={"text": "Second"})
    store.update_scene_render_settings(
        first["id"], reveal_duration=1.0, hold_duration=0.5, settings={"style": "whiteboard"}
    )
    store.update_scene_render_settings(
        second["id"], reveal_duration=1.0, hold_duration=0.5, settings={"style": "color_reveal"}
    )
    return store, first, second


def _exporter(store, media, render_calls):
    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"png")
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        del kwargs
        render_calls.append(("whiteboard", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def video(plan, output, **kwargs):
        del kwargs
        render_calls.append(("video", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    return ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
        video_renderer=video,
    )


def test_project_exporter_preflights_unrecovered_timeline_tracks_before_any_render(tmp_path):
    store, _first, _second = _store(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {"legacy": {"start": 0.0}},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [],
        },
    )
    media = FakeMediaExporter()
    render_calls = []

    with pytest.raises(UnsupportedProjectTimeline, match="clips"):
        _exporter(store, media, render_calls).export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []


def test_project_exporter_preflights_invalid_media_order_before_any_render(tmp_path):
    store, first, _second = _store(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"]],
        },
    )
    media = FakeMediaExporter()
    render_calls = []

    with pytest.raises(UnsupportedProjectTimeline, match="mediaOrder"):
        _exporter(store, media, render_calls).export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert media.calls == []



@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("clips", []),
        ("videoClips", {}),
        ("audioClips", {}),
        ("mediaOrder", {}),
    ],
    ids=[
        "clips-must-be-mapping",
        "video-clips-must-be-list",
        "audio-clips-must-be-list",
        "media-order-must-be-list",
    ],
)
def test_project_exporter_rejects_empty_wrong_shape_timeline_bucket_before_any_render(
    tmp_path,
    field,
    value,
):
    store, _first, _second = _store(tmp_path)
    state = {
        "clips": {},
        "videoClips": [],
        "audioClips": [],
        "mediaOrder": [],
    }
    state[field] = value
    store.save_timeline("p1", state)

    media = FakeMediaExporter()
    render_calls = []

    with pytest.raises(UnsupportedProjectTimeline, match=field):
        _exporter(store, media, render_calls).export(
            "p1",
            tmp_path / f"never-{field}.mp4",
        )

    assert render_calls == []
    assert media.calls == []


def test_project_exporter_accepts_empty_timeline_buckets_with_canonical_shapes(tmp_path):
    store, _first, _second = _store(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [],
        },
    )
    media = FakeMediaExporter()
    render_calls = []

    result = _exporter(store, media, render_calls).export(
        "p1",
        tmp_path / "canonical-empty-timeline.mp4",
    )

    assert result == tmp_path / "canonical-empty-timeline.mp4"
    assert render_calls != []
    assert len(media.calls) == 1



def test_project_exporter_rejects_duplicate_persisted_scene_positions_before_any_render(tmp_path):
    store, _first, second = _store(tmp_path)
    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_scenes SET position=0 WHERE id=?",
            (second["id"],),
        )

    media = FakeMediaExporter()
    render_calls = []
    output = tmp_path / "never-duplicate-scene-position.mp4"

    with pytest.raises(
        UnsupportedProjectTimeline,
        match=r"^scene position 0 must be unique$",
    ):
        try:
            _exporter(store, media, render_calls).export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()



def test_project_exporter_rejects_blank_persisted_scene_id_before_any_render(tmp_path):
    store, _first, second = _store(tmp_path)
    with store._connect() as conn:
        conn.execute(
            "DELETE FROM visual_editor_objects WHERE scene_id=?",
            (second["id"],),
        )
        conn.execute(
            "UPDATE visual_editor_scenes SET id='   ' WHERE id=?",
            (second["id"],),
        )

    media = FakeMediaExporter()
    render_calls = []
    output = tmp_path / "never-blank-scene-id.mp4"

    with pytest.raises(
        UnsupportedProjectTimeline,
        match=r"^scene id must not be blank$",
    ):
        try:
            _exporter(store, media, render_calls).export("p1", output)
        finally:
            assert render_calls == []
            assert media.calls == []
            assert not output.exists()
