from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.video_compositor import SceneVideoCompositor, UnsupportedVideoComposition
from nolane_studio.storage.store import ProjectStore


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def export(self, clips, output, **kwargs):
        self.calls.append((list(clips), Path(output), kwargs))
        Path(output).touch()
        return Path(output)


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        del timeout
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


def test_project_exporter_preflights_later_multiple_video_scene_before_any_render(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Multiple video preflight")
    store.replace_scenes("p1", [Scene(0, "First"), Scene(1, "Second")])
    first, second = store.list_scenes("p1")

    store.add_visual_object(
        first["id"],
        "shape",
        name="First shape",
        payload={"fill": "#FF0000"},
    )
    store.update_scene_render_settings(
        first["id"],
        reveal_duration=0.0,
        hold_duration=1.0,
        settings={"style": "static"},
    )

    first_video = tmp_path / "first-video.mp4"
    second_video = tmp_path / "second-video.mp4"
    first_video.touch()
    second_video.touch()
    store.add_visual_object(
        second["id"],
        "video",
        name="Video one",
        source=str(first_video),
    )
    store.add_visual_object(
        second["id"],
        "video",
        name="Video two",
        source=str(second_video),
    )
    store.update_scene_render_settings(
        second["id"],
        reveal_duration=0.0,
        hold_duration=1.0,
        settings={"style": "static"},
    )

    media = FakeMediaExporter()
    render_calls: list[tuple[str, str]] = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_bytes(b"png")
        return Path(output)

    runner = FakeRunner()

    def layer_renderer(plan, output, **kwargs):
        del plan, kwargs
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: True,
        layer_renderer=layer_renderer,
    )

    def video(plan, output, **kwargs):
        render_calls.append(("video", plan.scene_id))
        return compositor.render(plan, output, **kwargs)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video,
    )

    with pytest.raises(UnsupportedVideoComposition, match="multiple"):
        exporter.export("p1", tmp_path / "never.mp4")

    assert render_calls == []
    assert runner.commands == []
    assert media.calls == []
