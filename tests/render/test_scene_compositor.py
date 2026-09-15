from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QImage

from nolane_studio.render.compositor import CompositionRequiresVideo, render_scene_snapshot
from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.scene_plan import SceneRenderPlan


def _plan(objects):
    return SceneRenderPlan(
        scene_id="scene-1",
        position=0,
        text="Scene",
        objects=tuple(objects),
        profile=RenderProfile(style="static", reveal_duration=0.0, hold_duration=2.0),
        object_timing=(),
        total_duration=2.0,
        media_sources=tuple(
            str(obj.get("source")) for obj in objects if obj.get("kind") in {"image", "video"} and obj.get("source")
        ),
    )


def test_compositor_renders_shape_drawing_and_image_in_z_order(tmp_path):
    source = tmp_path / "source.png"
    image = QImage(20, 20, QImage.Format.Format_ARGB32)
    image.fill(QColor("#0055FF"))
    assert image.save(str(source))

    plan = _plan(
        [
            {
                "id": "shape",
                "kind": "shape",
                "x": 0,
                "y": 0,
                "width": 240,
                "height": 180,
                "rotation": 0,
                "opacity": 1,
                "z_index": 0,
                "payload": {"fill": "#FF0000"},
            },
            {
                "id": "image",
                "kind": "image",
                "source": str(source),
                "x": 40,
                "y": 40,
                "width": 80,
                "height": 80,
                "rotation": 0,
                "opacity": 1,
                "z_index": 1,
                "payload": {},
            },
            {
                "id": "drawing",
                "kind": "drawing",
                "x": 0,
                "y": 0,
                "width": 1280,
                "height": 720,
                "rotation": 0,
                "opacity": 1,
                "z_index": 2,
                "payload": {"points": [[10, 150], [150, 150]], "color": "#000000", "stroke": 8},
            },
        ]
    )
    output = tmp_path / "scene.png"

    render_scene_snapshot(plan, output)

    rendered = QImage(str(output))
    assert not rendered.isNull()
    assert (rendered.width(), rendered.height()) == (1280, 720)
    assert rendered.pixelColor(10, 10).name().upper() == "#FF0000"
    assert rendered.pixelColor(60, 60).name().upper() == "#0055FF"
    assert rendered.pixelColor(80, 150).value() < 30
    assert rendered.pixelColor(900, 600).name().upper() == "#F5F3EC"


def test_compositor_honors_object_opacity(tmp_path):
    plan = _plan(
        [
            {
                "id": "shape",
                "kind": "shape",
                "x": 0,
                "y": 0,
                "width": 100,
                "height": 100,
                "rotation": 0,
                "opacity": 0.5,
                "z_index": 0,
                "payload": {"fill": "#000000"},
            }
        ]
    )
    output = tmp_path / "opacity.png"

    render_scene_snapshot(plan, output)

    rendered = QImage(str(output))
    pixel = rendered.pixelColor(50, 50)
    assert 90 <= pixel.red() <= 150
    assert 90 <= pixel.green() <= 150
    assert 90 <= pixel.blue() <= 150


def test_compositor_refuses_to_silently_drop_video_layers(tmp_path):
    plan = _plan(
        [
            {
                "id": "video",
                "kind": "video",
                "source": "clip.mp4",
                "x": 0,
                "y": 0,
                "width": 1280,
                "height": 720,
                "rotation": 0,
                "opacity": 1,
                "z_index": 0,
                "payload": {},
            }
        ]
    )

    with pytest.raises(CompositionRequiresVideo):
        render_scene_snapshot(plan, tmp_path / "never.png")
