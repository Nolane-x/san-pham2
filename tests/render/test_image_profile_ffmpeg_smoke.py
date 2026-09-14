from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPainter

from nolane_studio.render.effects import RenderProfile
from nolane_studio.render.exporter import build_image_segment_command, resolve_ffmpeg_exe
from nolane_studio.render.ffmpeg import SubprocessRunner


def _save_fixture(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    try:
        painter.fillRect(width // 4, height // 4, width // 2, height // 2, QColor("#7C5CFC"))
    finally:
        painter.end()
    assert image.save(str(path))


@pytest.mark.parametrize("style", ["whiteboard", "color_reveal"])
def test_real_ffmpeg_recovered_image_profile_smoke(tmp_path, style):
    width, height, fps = 64, 36, 12
    source = tmp_path / f"{style}.png"
    output = tmp_path / f"{style}.mp4"
    _save_fixture(source, width, height)

    profile = RenderProfile(
        style=style,
        camera="static",
        reveal_duration=0.25,
        hold_duration=0.25,
    )
    command = build_image_segment_command(
        resolve_ffmpeg_exe(),
        str(source),
        str(output),
        duration=0.5,
        width=width,
        height=height,
        fps=fps,
        profile=profile,
    )
    SubprocessRunner().run(command, timeout=30)

    assert output.is_file()
    assert output.stat().st_size > 1000
