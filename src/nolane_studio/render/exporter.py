from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from nolane_studio.domain import TransitionSpec

from .effects import (
    RenderProfile,
    build_image_filter_graph,
    normalize_ffmpeg_fps,
    normalize_ffmpeg_render_geometry,
)
from .ffmpeg import SubprocessRunner
from .timeline import build_transition_gaps


@dataclass(frozen=True, slots=True)
class ExportClip:
    path: str
    kind: str
    duration: float = 6.0
    trim_start: float = 0.0
    trim_end: float | None = None
    speed: float = 1.0
    render_profile: Mapping[str, object] | None = None
    clip_id: str = ""
    narration_audio: str | None = None

    def __post_init__(self) -> None:
        kind = self.kind.strip().lower()
        if kind not in {"image", "video"}:
            raise ValueError("kind must be image or video")
        if kind == "image" and not math.isfinite(self.duration):
            raise ValueError("image duration must be finite")
        if kind == "image" and self.duration <= 0:
            raise ValueError("image duration must be > 0")
        if kind == "video":
            if not math.isfinite(self.trim_start):
                raise ValueError("trim_start must be finite")
            if self.trim_end is not None and not math.isfinite(self.trim_end):
                raise ValueError("trim_end must be finite")
            if not math.isfinite(self.speed):
                raise ValueError("speed must be finite")
        if self.trim_start < 0:
            raise ValueError("trim_start must be >= 0")
        if self.trim_end is not None and self.trim_end <= self.trim_start:
            raise ValueError("trim_end must be greater than trim_start")
        if self.speed <= 0:
            raise ValueError("speed must be > 0")
        narration = None if self.narration_audio is None else str(self.narration_audio).strip()
        if narration == "":
            narration = None
        if narration is not None:
            if not math.isfinite(self.duration):
                raise ValueError("narrated clip duration must be finite")
            if self.duration <= 0:
                raise ValueError("narrated clip duration must be > 0")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "clip_id", str(self.clip_id).strip())
        object.__setattr__(self, "narration_audio", narration)


def resolve_ffmpeg_exe() -> str:
    """Prefer the wheel-bundled FFmpeg binary and fall back to PATH."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _video_filter(width: int, height: int, fps: int) -> str:
    width, height, fps = normalize_ffmpeg_render_geometry(width, height, fps)
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"fps={fps},setsar=1"
    )


def _atempo_filter(speed: float) -> str:
    speed = float(speed)
    if not math.isfinite(speed):
        raise ValueError("speed must be finite")
    if speed <= 0:
        raise ValueError("speed must be > 0")
    factors: list[float] = []
    while speed > 2.0:
        factors.append(2.0)
        speed /= 2.0
    while speed < 0.5:
        factors.append(0.5)
        speed /= 0.5
    factors.append(speed)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def _narration_filter_chain(
    input_label: str,
    *,
    duration: float,
    trim_start: float = 0.0,
    trim_end: float | None = None,
    speed: float = 1.0,
    output_label: str = "narration",
) -> str:
    """Build narration filtering that follows the same clip window and speed."""
    duration = float(duration)
    trim_start = float(trim_start)
    speed = float(speed)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration must be finite and > 0")
    if not math.isfinite(trim_start) or trim_start < 0:
        raise ValueError("trim_start must be finite and >= 0")
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("speed must be finite and > 0")

    parts: list[str] = []
    if trim_end is not None:
        trim_end = float(trim_end)
        if not math.isfinite(trim_end):
            raise ValueError("trim_end must be finite")
        if trim_end <= trim_start:
            raise ValueError("trim_end must be greater than trim_start")
        parts.append(f"atrim=start={trim_start:.6f}:end={trim_end:.6f}")
        parts.append("asetpts=PTS-STARTPTS")
    elif trim_start:
        parts.append(f"atrim=start={trim_start:.6f}")
        parts.append("asetpts=PTS-STARTPTS")

    if speed != 1.0:
        parts.append(_atempo_filter(speed))
    parts.extend(
        [
            "aresample=48000",
            "apad",
            f"atrim=duration={duration:.6f}",
        ]
    )
    return f"{input_label}{','.join(parts)}[{output_label}]"


def build_image_segment_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    duration: float,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    profile: RenderProfile | None = None,
    narration_audio: str | None = None,
    trim_start: float = 0.0,
    trim_end: float | None = None,
    speed: float = 1.0,
) -> list[str]:
    duration = float(duration)
    if not math.isfinite(duration):
        raise ValueError("duration must be finite")
    if duration <= 0:
        raise ValueError("duration must be > 0")
    narration = None if narration_audio is None else str(narration_audio).strip()
    if narration == "":
        narration = None

    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        source,
    ]
    if narration is None:
        cmd += [
            "-f",
            "lavfi",
            "-t",
            f"{duration:.6f}",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
        ]
        if profile is None:
            cmd += ["-map", "0:v:0", "-map", "1:a:0", "-vf", _video_filter(width, height, fps)]
        else:
            cmd += [
                "-filter_complex",
                build_image_filter_graph(width, height, fps, profile, total_duration=duration),
                "-map",
                "[outv]",
                "-map",
                "1:a:0",
            ]
    else:
        cmd += ["-i", narration]
        narration_graph = _narration_filter_chain(
            "[1:a]",
            duration=duration,
            trim_start=trim_start,
            trim_end=trim_end,
            speed=speed,
        )
        if profile is None:
            cmd += [
                "-filter_complex",
                narration_graph,
                "-map",
                "0:v:0",
                "-map",
                "[narration]",
                "-vf",
                _video_filter(width, height, fps),
            ]
        else:
            graph = (
                build_image_filter_graph(width, height, fps, profile, total_duration=duration)
                + ";"
                + narration_graph
            )
            cmd += [
                "-filter_complex",
                graph,
                "-map",
                "[outv]",
                "-map",
                "[narration]",
            ]
    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-shortest", "-movflags", "+faststart", output,
    ]
    return cmd


def build_video_segment_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    has_audio: bool,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
    trim_start: float = 0.0,
    trim_end: float | None = None,
    speed: float = 1.0,
    duration: float | None = None,
    narration_audio: str | None = None,
) -> list[str]:
    trim_start = float(trim_start)
    speed = float(speed)
    if not math.isfinite(trim_start):
        raise ValueError("trim_start must be finite")
    if not math.isfinite(speed):
        raise ValueError("speed must be finite")
    if trim_start < 0:
        raise ValueError("trim_start must be >= 0")
    if speed <= 0:
        raise ValueError("speed must be > 0")

    narration = None if narration_audio is None else str(narration_audio).strip()
    if narration == "":
        narration = None
    narration_duration: float | None = None
    if narration is not None:
        if duration is None:
            raise ValueError("duration is required when narration_audio is set")
        narration_duration = float(duration)
        if not math.isfinite(narration_duration):
            raise ValueError("duration must be finite")
        if narration_duration <= 0:
            raise ValueError("duration must be > 0")

    cmd = [ffmpeg, "-y"]
    if trim_start:
        cmd += ["-ss", f"{trim_start:.6f}"]
    if trim_end is not None:
        trim_end = float(trim_end)
        if not math.isfinite(trim_end):
            raise ValueError("trim_end must be finite")
        if trim_end <= trim_start:
            raise ValueError("trim_end must be greater than trim_start")
        cmd += ["-t", f"{trim_end - trim_start:.6f}"]
    cmd += ["-i", source]

    if narration is not None:
        cmd += ["-i", narration]
    elif not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]

    cmd += ["-map", "0:v:0"]
    video_filter = _video_filter(width, height, fps)
    if speed != 1.0:
        video_filter += f",setpts=PTS/{speed:.6f}"

    if narration is None:
        cmd += ["-map", "0:a:0?" if has_audio else "1:a:0", "-vf", video_filter]
        if has_audio and speed != 1.0:
            cmd += ["-af", _atempo_filter(speed)]
    else:
        assert narration_duration is not None
        narration_chain = _narration_filter_chain(
            "[1:a]",
            duration=narration_duration,
            trim_start=trim_start,
            trim_end=trim_end,
            speed=speed,
        )
        if has_audio:
            source_filters: list[str] = []
            if speed != 1.0:
                source_filters.append(_atempo_filter(speed))
            source_filters.extend(
                [
                    "aresample=48000",
                    "apad",
                    f"atrim=duration={narration_duration:.6f}",
                ]
            )
            source_chain = f"[0:a]{','.join(source_filters)}[sourcea]"
            mix_chain = (
                f"[sourcea][narration]amix=inputs=2:duration=longest:"
                f"dropout_transition=0,atrim=duration={narration_duration:.6f}[mixeda]"
            )
            audio_graph = ";".join((source_chain, narration_chain, mix_chain))
            audio_map = "[mixeda]"
        else:
            audio_graph = narration_chain
            audio_map = "[narration]"
        cmd += [
            "-filter_complex",
            audio_graph,
            "-map",
            audio_map,
            "-vf",
            video_filter,
            "-t",
            f"{narration_duration:.6f}",
        ]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1", "-crf", "20",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-shortest", "-movflags", "+faststart", output,
    ]
    return cmd


def build_transition_segment_command(
    ffmpeg: str,
    left: str,
    right: str,
    output: str,
    *,
    effect: str = "fade",
    duration: float = 0.5,
    fps: int = 24,
) -> list[str]:
    duration = float(duration)
    if not 0.1 <= duration <= 10.0:
        raise ValueError("transition duration must be between 0.1 and 10 seconds")
    fps = normalize_ffmpeg_fps(fps)
    effect = str(effect).strip().lower()
    allowed = {"fade", "wipeleft", "wiperight", "slideleft", "slideright", "smoothleft", "smoothright"}
    if effect not in allowed:
        effect = "fade"
    graph = (
        f"[0:v]trim=duration=0.050000,setpts=PTS-STARTPTS,fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={duration:.6f}[left];"
        f"[1:v]trim=duration=0.050000,setpts=PTS-STARTPTS,fps={fps},"
        f"tpad=stop_mode=clone:stop_duration={duration:.6f}[right];"
        f"[left][right]xfade=transition={effect}:duration={duration:.6f}:offset=0[outv]"
    )
    return [
        ffmpeg, "-y",
        "-sseof", "-0.050000", "-i", left,
        "-i", right,
        "-f", "lavfi", "-t", f"{duration:.6f}", "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex", graph,
        "-map", "[outv]", "-map", "2:a:0",
        "-t", f"{duration:.6f}",
        "-c:v", "libx264", "-preset", "veryfast", "-threads", "1", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-ar", "48000", "-ac", "2", "-movflags", "+faststart", output,
    ]


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
    """Deterministic low-memory timeline exporter.

    Clips are normalized sequentially. Transitions are separate normalized
    segments inserted *between* clips, preserving the recovered additive
    duration semantics instead of shortening clips through overlap.
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
        transitions: Sequence[TransitionSpec] = (),
    ) -> Path:
        clips = list(clips)
        if not clips:
            raise ValueError("at least one media clip is required")
        normalize_ffmpeg_render_geometry(width, height, fps)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        clip_ids = [clip.clip_id or str(index) for index, clip in enumerate(clips)]
        build_transition_gaps(clip_ids, transitions)
        transition_lookup = {(t.from_id, t.to_id): t for t in transitions}

        with tempfile.TemporaryDirectory(prefix="nolane-studio-export-") as temp_raw:
            temp = Path(temp_raw)
            normalized: list[Path] = []
            for index, clip in enumerate(clips):
                segment = temp / f"segment-{index:04d}.mp4"
                if clip.kind == "image":
                    profile = RenderProfile(**dict(clip.render_profile)) if clip.render_profile else None
                    command = build_image_segment_command(
                        self.ffmpeg, clip.path, str(segment), duration=clip.duration,
                        width=width, height=height, fps=fps, profile=profile,
                        narration_audio=clip.narration_audio,
                        trim_start=clip.trim_start, trim_end=clip.trim_end, speed=clip.speed,
                    )
                else:
                    command = build_video_segment_command(
                        self.ffmpeg, clip.path, str(segment),
                        has_audio=self.audio_probe(clip.path), width=width, height=height, fps=fps,
                        trim_start=clip.trim_start, trim_end=clip.trim_end, speed=clip.speed,
                        duration=clip.duration if clip.narration_audio else None,
                        narration_audio=clip.narration_audio,
                    )
                self.runner.run(command)
                normalized.append(segment)

            assembly: list[Path] = []
            for index, segment in enumerate(normalized):
                assembly.append(segment)
                if index >= len(normalized) - 1:
                    continue
                pair = (clip_ids[index], clip_ids[index + 1])
                transition = transition_lookup.get(pair)
                if transition is None:
                    continue
                trans_segment = temp / f"transition-{index:04d}.mp4"
                self.runner.run(
                    build_transition_segment_command(
                        self.ffmpeg,
                        str(segment),
                        str(normalized[index + 1]),
                        str(trans_segment),
                        effect=transition.effect,
                        duration=transition.duration,
                        fps=fps,
                    )
                )
                assembly.append(trans_segment)

            concat_file = temp / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{_concat_escape(segment)}'\n" for segment in assembly),
                encoding="utf-8",
            )
            self.runner.run(
                [
                    self.ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                    "-c", "copy", "-movflags", "+faststart", str(output),
                ]
            )
        return output
