from __future__ import annotations

from pathlib import Path

from nolane_studio.domain import TransitionSpec
from nolane_studio.render.exporter import ExportClip, MediaExporter, build_transition_segment_command


def test_transition_command_builds_standalone_additive_segment():
    cmd = build_transition_segment_command(
        "ffmpeg",
        "left.mp4",
        "right.mp4",
        "transition.mp4",
        effect="wipeleft",
        duration=0.75,
    )
    joined = " ".join(cmd)
    assert "-sseof" in cmd
    assert "xfade=transition=wipeleft:duration=0.750000:offset=0" in joined
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in joined
    assert "-t 0.750000" in joined


class FakeRunner:
    def __init__(self):
        self.commands: list[list[str]] = []

    def run(self, command, *, timeout=None):
        self.commands.append(list(command))
        output = Path(command[-1])
        if output.suffix == ".mp4":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.touch()


def test_exporter_interleaves_transition_as_its_own_segment(tmp_path):
    runner = FakeRunner()
    exporter = MediaExporter(ffmpeg="ffmpeg", runner=runner, audio_probe=lambda _: False)
    output = tmp_path / "final.mp4"
    exporter.export(
        [
            ExportClip("a.png", "image", 3.0, clip_id="a"),
            ExportClip("b.png", "image", 4.0, clip_id="b"),
        ],
        output,
        transitions=[TransitionSpec("a", "b", "fade", 0.5)],
    )
    transition_commands = [cmd for cmd in runner.commands if any("xfade=transition=fade" in token for token in cmd)]
    assert len(transition_commands) == 1
    # 2 normalized clips + 1 additive transition + final concat.
    assert len(runner.commands) == 4
