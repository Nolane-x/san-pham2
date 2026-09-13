from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .ffmpeg import SubprocessRunner


@dataclass(frozen=True, slots=True)
class ExportClip:
    path: str
    kind: str
    duration: float = 6.0

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()
        if kind not in {"image", "video"}:
            raise ValueError("kind must be image or video")
        if kind == "image" and self.duration <= 0:
            raise ValueError("image duration must be > 0")
        object.__setattr__(self, "kind", kind)


def resolve_ffmpeg_exe() -> str:
    """Prefer the wheel-bundled FFmpeg binary and fall back to PATH."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _video_filter(width: int, height: int, fps: int) -> str:
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"fps={int(fps)},setsar=1"
    )


def build_image_segment_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    duration: float,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    return [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{float(duration):.6f}",
        "-i",
        source,
        "-f",
        "lavfi",
        "-t",
        f"{float(duration):.6f}",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        _video_filter(width, height, fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-threads",
        "1",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        output,
    ]


def build_video_segment_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    has_audio: bool,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    cmd = [ffmpeg, "-y", "-i", source]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    cmd += ["-map", "0:v:0", "-map", "0:a:0?" if has_audio else "1:a:0"]
    cmd += [
        "-vf",
        _video_filter(width, height, fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-threads",
        "1",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "high",
        "-level",
        "4.1",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-shortest",
        "-movflags",
        "+faststart",
        output,
    ]
    return cmd


def probe_has_audio(ffmpeg: str, path: str) -> bool:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    text = (result.stderr or "") + "\n" + (result.stdout or "")
    return " Audio: " in text or "Audio:" in text


def _concat_escape(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


class MediaExporter:
    """Small, deterministic mixed image/video exporter for the desktop release.

    Every source is normalized to the same A/V stream shape before concat so the
    final operation is stable and does not require keeping decoded frames in RAM.
    """

    def __init__(
        self,
        *,
        ffmpeg: str | None = None,
        runner: SubprocessRunner | None = None,
        audio_probe: Callable[[str], bool] | None = None,
    ) -> None:
        self.ffmpeg = ffmpeg or resolve_ffmpeg_exe()
        self.runner = runner or SubprocessRunner()
        self.audio_probe = audio_probe or (lambda path: probe_has_audio(self.ffmpeg, path))

    def export(
        self,
        clips: Sequence[ExportClip] | Iterable[ExportClip],
        output: str | Path,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
    ) -> Path:
        clips = list(clips)
        if not clips:
            raise ValueError("at least one media clip is required")
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="nolane-studio-export-") as temp_raw:
            temp = Path(temp_raw)
            segments: list[Path] = []
            for index, clip in enumerate(clips):
                segment = temp / f"segment-{index:04d}.mp4"
                if clip.kind == "image":
                    command = build_image_segment_command(
                        self.ffmpeg,
                        clip.path,
                        str(segment),
                        duration=clip.duration,
                        width=width,
                        height=height,
                        fps=fps,
                    )
                else:
                    command = build_video_segment_command(
                        self.ffmpeg,
                        clip.path,
                        str(segment),
                        has_audio=self.audio_probe(clip.path),
                        width=width,
                        height=height,
                        fps=fps,
                    )
                self.runner.run(command)
                segments.append(segment)

            concat_file = temp / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{_concat_escape(segment)}'\n" for segment in segments),
                encoding="utf-8",
            )
            self.runner.run(
                [
                    self.ffmpeg,
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_file),
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
            )
        return output
