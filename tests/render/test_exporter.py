from pathlib import Path

from nolane_studio.render.exporter import (
    ExportClip,
    MediaExporter,
    build_image_segment_command,
    build_video_segment_command,
)


def test_image_segment_command_adds_silent_audio_for_concat_compatibility():
    cmd = build_image_segment_command("ffmpeg", "image.png", "scene.mp4", duration=5.0)
    joined = " ".join(cmd)
    assert "-loop 1" in joined
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in joined
    assert "libx264" in joined
    assert "aac" in joined
    assert cmd[-1] == "scene.mp4"


def test_video_segment_command_can_preserve_source_audio():
    cmd = build_video_segment_command("ffmpeg", "clip.mp4", "scene.mp4", has_audio=True)
    assert "0:a:0?" in cmd
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" not in cmd


class FakeRunner:
    def __init__(self):
        self.commands = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        if output.suffix == ".mp4":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.touch()


def test_exporter_normalizes_each_clip_then_concats(tmp_path):
    runner = FakeRunner()
    exporter = MediaExporter(
        ffmpeg="ffmpeg",
        runner=runner,
        audio_probe=lambda path: path.endswith("with-audio.mp4"),
    )
    output = tmp_path / "final.mp4"
    exporter.export(
        [
            ExportClip("cover.png", "image", 4.0),
            ExportClip("with-audio.mp4", "video"),
        ],
        output,
    )
    assert output.exists()
    assert len(runner.commands) == 3
    assert runner.commands[-1][-1] == str(output)
    concat_file = Path(runner.commands[-1][runner.commands[-1].index("-i") + 1])
    assert concat_file.name == "concat.txt"
