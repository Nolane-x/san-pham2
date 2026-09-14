from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from nolane_studio.render.exporter import (
    build_image_segment_command,
    build_transition_segment_command,
    resolve_ffmpeg_exe,
)
from nolane_studio.render.ffmpeg import SubprocessRunner


def _save_solid(path: Path, width: int, height: int, color: str) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    assert image.save(str(path))


def _render_source_clip(
    ffmpeg: str,
    runner: SubprocessRunner,
    source: Path,
    output: Path,
    *,
    width: int,
    height: int,
    fps: int,
) -> None:
    runner.run(
        build_image_segment_command(
            ffmpeg,
            str(source),
            str(output),
            duration=0.5,
            width=width,
            height=height,
            fps=fps,
        ),
        timeout=30,
    )


def test_real_ffmpeg_additive_transition_smoke(tmp_path):
    width, height, fps = 64, 36, 12
    ffmpeg = resolve_ffmpeg_exe()
    runner = SubprocessRunner()

    left_image = tmp_path / "left.png"
    right_image = tmp_path / "right.png"
    left_clip = tmp_path / "left.mp4"
    right_clip = tmp_path / "right.mp4"
    transition = tmp_path / "transition.mp4"

    _save_solid(left_image, width, height, "#7C5CFC")
    _save_solid(right_image, width, height, "#21C55D")
    _render_source_clip(ffmpeg, runner, left_image, left_clip, width=width, height=height, fps=fps)
    _render_source_clip(ffmpeg, runner, right_image, right_clip, width=width, height=height, fps=fps)

    command = build_transition_segment_command(
        ffmpeg,
        str(left_clip),
        str(right_clip),
        str(transition),
        effect="fade",
        duration=0.25,
        fps=fps,
    )
    runner.run(command, timeout=30)

    assert transition.is_file()
    assert transition.stat().st_size > 1000
