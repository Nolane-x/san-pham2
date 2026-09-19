from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import Scene
from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import SceneVideoCompositor, UnsupportedVideoComposition
from nolane_studio.storage.store import ProjectStore


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()


class FakeMediaExporter:
    def __init__(self):
        self.calls = []

    def export(self, clips, output, **kwargs):
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs, [Path(clip.path).exists() for clip in clips]))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _plan(objects, *, duration=5.0):
    return SceneRenderPlan(
        scene_id="scene-video",
        position=0,
        text="Video scene",
        objects=tuple(objects),
        profile=RenderProfile(style="static", reveal_duration=0.0, hold_duration=duration),
        object_timing=(),
        total_duration=duration,
        media_sources=tuple(
            str(obj.get("source"))
            for obj in objects
            if obj.get("kind") in {"image", "video"} and obj.get("source")
        ),
    )


def _touch_layer(actual_plan, output, *, objects, transparent, width, height):
    del actual_plan, objects, transparent, width, height
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).touch()
    return Path(output)


def test_video_compositor_preserves_static_layers_below_and_above_video(tmp_path):
    video = tmp_path / "clip.mp4"
    video.touch()
    plan = _plan(
        [
            {"id": "back", "kind": "shape", "z_index": 0, "visible": True, "payload": {"fill": "#FFFFFF"}},
            {
                "id": "video",
                "kind": "video",
                "source": str(video),
                "x": 120,
                "y": 80,
                "width": 640,
                "height": 360,
                "rotation": 0,
                "opacity": 0.75,
                "z_index": 1,
                "visible": True,
                "payload": {},
            },
            {"id": "caption", "kind": "text", "z_index": 2, "visible": True, "payload": {"text": "Top"}},
        ]
    )
    rendered_layers = []

    def layer_renderer(actual_plan, output, *, objects, transparent, width, height):
        rendered_layers.append(([obj["id"] for obj in objects], transparent, width, height))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    runner = FakeRunner()
    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: True,
        layer_renderer=layer_renderer,
    )
    output = tmp_path / "scene.mp4"

    result = compositor.render(plan, output, width=1280, height=720, fps=24)

    assert result == output
    assert rendered_layers == [
        (["back"], False, 1280, 720),
        (["caption"], True, 1280, 720),
    ]
    assert len(runner.commands) == 1
    joined = " ".join(runner.commands[0])
    assert str(video) in joined
    assert "scale=640:360" in joined
    assert "overlay=x=120:y=80" in joined
    assert "colorchannelmixer=aa=0.750000" in joined
    assert "trim=duration=5.000000" in joined
    assert "0:a:0" not in joined
    assert "1:a:0?" in joined
    assert runner.commands[0][-1] == str(output)


def test_video_compositor_rotates_about_persisted_top_left_origin(tmp_path):
    video = tmp_path / "rotated.mp4"
    video.touch()
    plan = _plan(
        [
            {
                "id": "video",
                "kind": "video",
                "source": str(video),
                "x": 120,
                "y": 80,
                "width": 640,
                "height": 360,
                "rotation": 90,
                "opacity": 0.75,
                "z_index": 0,
                "visible": True,
                "payload": {},
            }
        ]
    )
    runner = FakeRunner()
    compositor = SceneVideoCompositor(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: True,
        layer_renderer=_touch_layer,
    )

    result = compositor.render(plan, tmp_path / "rotated-out.mp4")

    assert result.is_file()
    assert len(runner.commands) == 1
    joined = " ".join(runner.commands[0])
    assert "format=rgba" in joined
    assert "rotate=1.570796327" in joined
    assert "ow='rotw(iw)'" in joined
    assert "oh='roth(ih)'" in joined
    # Canvas/QPainter rotates around the object's local (0, 0). For +90° the
    # 640x360 rectangle extends 360 px to the left while its top edge stays at y.
    assert "overlay=x=-240.000000:y=80.000000" in joined
    assert "1:a:0?" in joined


def test_video_compositor_rejects_multiple_video_layers_instead_of_dropping_one(tmp_path):
    first = tmp_path / "a.mp4"
    second = tmp_path / "b.mp4"
    first.touch()
    second.touch()
    plan = _plan(
        [
            {"id": "v1", "kind": "video", "source": str(first), "z_index": 0, "visible": True},
            {"id": "v2", "kind": "video", "source": str(second), "z_index": 1, "visible": True},
        ]
    )
    compositor = SceneVideoCompositor(ffmpeg="ffmpeg", runner=FakeRunner())

    with pytest.raises(UnsupportedVideoComposition, match="multiple"):
        compositor.render(plan, tmp_path / "never.mp4")


def test_project_scene_exporter_routes_video_scene_through_video_compositor(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Video project")
    store.replace_scenes("p1", [Scene(0, "Video")])
    scene = store.list_scenes("p1")[0]
    source = tmp_path / "source.mp4"
    source.touch()
    store.add_visual_object(scene["id"], "video", name="Source", source=str(source))

    media = FakeMediaExporter()
    video_calls = []

    def snapshot(*args, **kwargs):
        raise AssertionError("video scene must not use still snapshot compositor")

    def video_renderer(plan, output, *, width, height, fps):
        video_calls.append((plan.scene_id, width, height, fps))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        video_renderer=video_renderer,
    )
    output = tmp_path / "final.mp4"

    result = exporter.export("p1", output)

    assert result == output
    assert video_calls == [(scene["id"], 1280, 720, 24)]
    clips, called_output, kwargs, existed_during_call = media.calls[0]
    assert called_output == output
    assert existed_during_call == [True]
    assert len(clips) == 1
    assert clips[0].kind == "video"
    assert clips[0].clip_id == scene["id"]
    assert clips[0].trim_end == clips[0].duration
    assert kwargs == {"width": 1280, "height": 720, "fps": 24}
