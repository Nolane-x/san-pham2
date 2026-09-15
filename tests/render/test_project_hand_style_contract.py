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
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _scene_store(tmp_path, *, style: str, hand_style: str):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Hand style contract")
    store.replace_scenes("p1", [Scene(0, "Hand style")])
    scene = store.list_scenes("p1")[0]
    store.add_visual_object(
        scene["id"],
        "shape",
        name="Card",
        payload={"fill": "#FF0000"},
    )
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={"style": style, "hand_style": hand_style},
    )
    return store, scene


def _renderers(render_calls):
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

    return snapshot, whiteboard


@pytest.mark.parametrize("hand_style", ["hand-2.png", "hand-3.png"])
def test_project_exporter_fails_closed_for_unrendered_custom_whiteboard_hand_style(
    tmp_path, hand_style
):
    store, scene = _scene_store(tmp_path, style="whiteboard", hand_style=hand_style)
    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []
    snapshot, whiteboard = _renderers(render_calls)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )

    with pytest.raises(UnsupportedSceneRenderState, match="hand_style") as exc_info:
        exporter.export("p1", tmp_path / "never.mp4")

    assert scene["id"] in str(exc_info.value)
    assert render_calls == []
    assert media.calls == []


def test_project_exporter_keeps_recovered_default_whiteboard_hand_style_exportable(tmp_path):
    store, scene = _scene_store(tmp_path, style="whiteboard", hand_style="hand-1.png")
    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []
    snapshot, whiteboard = _renderers(render_calls)

    result = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    ).export("p1", tmp_path / "default-hand.mp4")

    assert result == tmp_path / "default-hand.mp4"
    assert render_calls == [("whiteboard", scene["id"])]
    assert len(media.calls) == 1


def test_project_exporter_does_not_apply_whiteboard_hand_guard_to_color_reveal(tmp_path):
    store, scene = _scene_store(tmp_path, style="color_reveal", hand_style="hand-3.png")
    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []
    snapshot, whiteboard = _renderers(render_calls)

    result = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    ).export("p1", tmp_path / "color-reveal.mp4")

    assert result == tmp_path / "color-reveal.mp4"
    assert render_calls == [("snapshot", scene["id"])]
    assert len(media.calls) == 1
