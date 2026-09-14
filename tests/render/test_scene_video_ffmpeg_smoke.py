from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter

from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.exporter import (
    build_image_segment_command,
    probe_has_audio,
    resolve_ffmpeg_exe,
)
from nolane_studio.render.ffmpeg import SubprocessRunner
from nolane_studio.render.scene_plan import SceneRenderPlan
from nolane_studio.render.video_compositor import SceneVideoCompositor


def _save_source_image(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#2463EB"))
    assert image.save(str(path))


def _layer_renderer(plan, output, *, objects, transparent, width, height):
    del plan, objects
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    if transparent:
        image.fill(QColor(0, 0, 0, 0))
    else:
        image.fill(QColor("white"))
        painter = QPainter(image)
        try:
            painter.fillRect(0, 0, max(1, width // 8), height, QColor("#111827"))
        finally:
            painter.end()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(output))
    return Path(output)


def test_real_ffmpeg_scene_video_compositor_preserves_source_audio(tmp_path):
    width, height, fps = 64, 36, 12
    ffmpeg = resolve_ffmpeg_exe()
    runner = SubprocessRunner()

    source_image = tmp_path / "source.png"
    source_video = tmp_path / "source.mp4"
    output = tmp_path / "scene-video.mp4"
    _save_source_image(source_image, width, height)
    runner.run(
        build_image_segment_command(
            ffmpeg,
            str(source_image),
            str(source_video),
            duration=0.5,
            width=width,
            height=height,
            fps=fps,
        ),
        timeout=30,
    )
    assert probe_has_audio(ffmpeg, str(source_video))

    plan = SceneRenderPlan(
        scene_id="scene-video-smoke",
        position=0,
        text="Video smoke",
        objects=(
            {
                "id": "video",
                "kind": "video",
                "source": str(source_video),
                "x": 8,
                "y": 4,
                "width": 48,
                "height": 28,
                "rotation": 0,
                "opacity": 0.8,
                "z_index": 0,
                "visible": True,
                "payload": {},
            },
        ),
        profile=RenderProfile(style="static", reveal_duration=0.0, hold_duration=0.5),
        object_timing=(),
        total_duration=0.5,
        media_sources=(str(source_video),),
    )

    compositor = SceneVideoCompositor(
        ffmpeg=ffmpeg,
        runner=runner,
        layer_renderer=_layer_renderer,
    )
    result = compositor.render(plan, output, width=width, height=height, fps=fps)

    assert result == output
    assert output.is_file()
    assert output.stat().st_size > 1000
    assert probe_has_audio(ffmpeg, str(output))
