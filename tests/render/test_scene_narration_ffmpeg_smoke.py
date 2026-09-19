from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from nolane_studio.render.exporter import (
    build_image_segment_command,
    build_video_segment_command,
    probe_has_audio,
    resolve_ffmpeg_exe,
)
from nolane_studio.render.ffmpeg import SubprocessRunner


def _save_solid(path: Path, width: int, height: int) -> None:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor("#2563EB"))
    assert image.save(str(path))


def _make_tone(ffmpeg: str, runner: SubprocessRunner, path: Path) -> None:
    runner.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=660:sample_rate=48000:duration=0.25",
            "-c:a",
            "pcm_s16le",
            str(path),
        ],
        timeout=30,
    )


def test_real_ffmpeg_image_scene_uses_persisted_narration(tmp_path):
    width, height, fps = 64, 36, 12
    ffmpeg = resolve_ffmpeg_exe()
    runner = SubprocessRunner()
    image = tmp_path / "scene.png"
    narration = tmp_path / "voice.wav"
    output = tmp_path / "narrated-image.mp4"

    _save_solid(image, width, height)
    _make_tone(ffmpeg, runner, narration)

    runner.run(
        build_image_segment_command(
            ffmpeg,
            str(image),
            str(output),
            duration=0.5,
            width=width,
            height=height,
            fps=fps,
            narration_audio=str(narration),
        ),
        timeout=30,
    )

    assert output.is_file()
    assert output.stat().st_size > 1000
    assert probe_has_audio(ffmpeg, str(output))


def test_real_ffmpeg_video_scene_mixes_source_audio_and_narration(tmp_path):
    width, height, fps = 64, 36, 12
    ffmpeg = resolve_ffmpeg_exe()
    runner = SubprocessRunner()
    image = tmp_path / "source.png"
    source = tmp_path / "source.mp4"
    narration = tmp_path / "voice.wav"
    output = tmp_path / "narrated-video.mp4"

    _save_solid(image, width, height)
    _make_tone(ffmpeg, runner, narration)
    runner.run(
        build_image_segment_command(
            ffmpeg,
            str(image),
            str(source),
            duration=0.5,
            width=width,
            height=height,
            fps=fps,
        ),
        timeout=30,
    )
    assert probe_has_audio(ffmpeg, str(source))

    runner.run(
        build_video_segment_command(
            ffmpeg,
            str(source),
            str(output),
            has_audio=True,
            width=width,
            height=height,
            fps=fps,
            trim_start=0.0,
            trim_end=0.5,
            duration=0.5,
            narration_audio=str(narration),
        ),
        timeout=30,
    )

    assert output.is_file()
    assert output.stat().st_size > 1000
    assert probe_has_audio(ffmpeg, str(output))
