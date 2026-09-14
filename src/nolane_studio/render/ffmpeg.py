from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class FFmpegPaths:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"


class SubprocessRunner:
    def run(self, command: Sequence[str], *, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            list(command), capture_output=True, text=True, timeout=timeout, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(f"media command failed ({result.returncode}): {result.stderr[-2000:]}")
        return result


def _even(value: int) -> int:
    value = max(2, int(value))
    return value if value % 2 == 0 else value - 1


def build_normalize_segment_command(
    paths: FFmpegPaths,
    source: str,
    output: str,
    *,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    width, height = _even(width), _even(height)
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"fps={int(fps)},setsar=1"
    )
    return [
        paths.ffmpeg, "-y", "-i", source,
        "-map", "0:v:0", "-an", "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1",
        "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", output,
    ]


def build_concat_command(paths: FFmpegPaths, concat_file: str, output: str) -> list[str]:
    return [
        paths.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c", "copy", "-movflags", "+faststart", output,
    ]


def build_global_audio_mux_command(
    paths: FFmpegPaths,
    video_path: str,
    audio_path: str,
    output_path: str,
    total_duration: float,
) -> list[str]:
    duration = max(0.0, float(total_duration))
    audio_filter = (
        "[1:a:0]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
        f"apad,atrim=0:{duration:.6f},asetpts=PTS-STARTPTS[aout]"
    )
    return [
        paths.ffmpeg, "-y", "-i", video_path, "-i", audio_path,
        "-filter_complex", audio_filter,
        "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart", output_path,
    ]
