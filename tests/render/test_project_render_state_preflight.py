from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter, UnsupportedSceneRenderState
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


def test_project_exporter_preflights_later_unsupported_render_state_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(first["id"], "shape", name="First shape", payload={"fill": "#FF0000"})
    store.add_visual_object(second["id"], "text", name="Second text", payload={"text": "Second"})
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "whiteboard"},
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": "color_reveal", "remove_background_enabled": True},
    )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

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

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
        video_renderer=video,
    )

    with pytest.raises(UnsupportedSceneRenderState, match="remove_background_enabled") as exc_info:
        exporter.export("p1", tmp_path / "never.mp4")

    assert second["id"] in str(exc_info.value)
    assert render_calls == []
    assert media.calls == []
