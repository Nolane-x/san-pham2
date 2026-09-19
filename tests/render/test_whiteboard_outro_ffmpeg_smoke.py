from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage, QPainter

from nolane_studio.render import whiteboard_compositor as whiteboard
from nolane_studio.render.exporter import resolve_ffmpeg_exe
from nolane_studio.render.ffmpeg import SubprocessRunner


def _save_scene(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    try:
        painter.fillRect(width // 4, height // 4, width // 2, height // 2, QColor("#7C5CFC"))
    finally:
        painter.end()
    assert image.save(str(path))


def test_real_ffmpeg_left_outro_smoke(tmp_path):
    builder = getattr(whiteboard, "build_scene_outro_command", None)
    assert builder is not None, "whiteboard outro FFmpeg builder is missing"

    width, height = 64, 36
    source = tmp_path / "scene.png"
    output = tmp_path / "outro.mp4"
    _save_scene(source, width, height)

    command = builder(
        resolve_ffmpeg_exe(),
        str(source),
        str(output),
        duration=0.25,
        direction="left",
        width=width,
        height=height,
        fps=12,
    )
    SubprocessRunner().run(command, timeout=30)

    assert output.is_file()
    assert output.stat().st_size > 1000
