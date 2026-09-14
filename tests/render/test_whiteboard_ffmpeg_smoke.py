from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter

from nolane_studio.render.exporter import resolve_ffmpeg_exe
from nolane_studio.render.ffmpeg import SubprocessRunner
from nolane_studio.render.whiteboard_compositor import build_object_push_command


def _save_base(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    assert image.save(str(path))


def _save_transparent_object(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    try:
        painter.fillRect(QRectF(width * 0.55, height * 0.25, width * 0.25, height * 0.5), QColor("#7C5CFC"))
    finally:
        painter.end()
    assert image.save(str(path))


def test_real_ffmpeg_from_left_push_smoke(tmp_path):
    width, height = 64, 36
    base = tmp_path / "base.png"
    object_layer = tmp_path / "object.png"
    output = tmp_path / "push.mp4"
    _save_base(base, width, height)
    _save_transparent_object(object_layer, width, height)

    command = build_object_push_command(
        resolve_ffmpeg_exe(),
        str(base),
        str(object_layer),
        str(output),
        duration=0.25,
        direction="from_left",
        width=width,
        height=height,
        fps=12,
    )
    SubprocessRunner().run(command, timeout=30)

    assert output.is_file()
    assert output.stat().st_size > 1000
