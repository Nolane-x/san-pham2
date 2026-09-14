from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .compositor import CompositionError, render_scene_layer_snapshot
from .exporter import probe_has_audio, resolve_ffmpeg_exe
from .ffmpeg import SubprocessRunner
from .scene_plan import SceneRenderPlan


class UnsupportedVideoComposition(CompositionError):
    """Raised when the persisted video layout cannot yet be reproduced safely."""


LayerRenderer = Callable[..., Path]
AudioProbe = Callable[[str], bool]


def _number(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _even(value: object, default: int) -> int:
    number = max(2, int(round(_number(value, default))))
    return number if number % 2 == 0 else number - 1


def _visible_objects(plan: SceneRenderPlan) -> list[dict[str, object]]:
    return sorted(
        (dict(obj) for obj in plan.objects if bool(obj.get("visible", True))),
        key=lambda obj: (int(obj.get("z_index", 0)), str(obj.get("id", ""))),
    )


class SceneVideoCompositor:
    """Compose one source-video layer between static persisted canvas bands.

    Supporting exactly one video layer keeps the first source-video path
    deterministic and lossless. Multiple videos are rejected explicitly until
    a true mixed-video timeline is implemented; no layer is ever dropped.
    """

    def __init__(
        self,
        *,
        ffmpeg: str | None = None,
        runner: SubprocessRunner | None = None,
        audio_probe: AudioProbe | None = None,
        layer_renderer: LayerRenderer = render_scene_layer_snapshot,
    ) -> None:
        self.ffmpeg = ffmpeg or resolve_ffmpeg_exe()
        self.runner = runner or SubprocessRunner()
        self.audio_probe = audio_probe or (lambda path: probe_has_audio(self.ffmpeg, path))
        self.layer_renderer = layer_renderer

    def render(
        self,
        plan: SceneRenderPlan,
        output: str | Path,
        *,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
    ) -> Path:
        ordered = _visible_objects(plan)
        video_indexes = [
            index
            for index, obj in enumerate(ordered)
            if str(obj.get("kind", "")).strip().lower() == "video"
        ]
        if not video_indexes:
            raise UnsupportedVideoComposition("scene does not contain a video layer")
        if len(video_indexes) > 1:
            raise UnsupportedVideoComposition("multiple video layers are not yet supported")

        video_index = video_indexes[0]
        video: Mapping[str, object] = ordered[video_index]
        source = Path(str(video.get("source") or ""))
        if not source.is_file():
            raise FileNotFoundError(f"scene video source not found: {source}")

        rotation = _number(video.get("rotation"), 0.0)
        if abs(rotation) > 1e-9:
            raise UnsupportedVideoComposition("rotated video layers are not yet supported")

        canvas_w = _even(width, 1280)
        canvas_h = _even(height, 720)
        video_w = _even(video.get("width"), 640)
        video_h = _even(video.get("height"), 360)
        x = int(round(_number(video.get("x"), 0.0)))
        y = int(round(_number(video.get("y"), 0.0)))
        opacity = max(0.0, min(1.0, _number(video.get("opacity"), 1.0)))
        total = max(0.001, float(plan.total_duration))
        fps = max(1, int(fps))

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="nolane-studio-video-scene-") as temp_raw:
            temp = Path(temp_raw)
            background = temp / "background.png"
            foreground = temp / "foreground.png"
            lower = ordered[:video_index]
            upper = ordered[video_index + 1 :]
            self.layer_renderer(
                plan,
                background,
                objects=lower,
                transparent=False,
                width=canvas_w,
                height=canvas_h,
            )
            self.layer_renderer(
                plan,
                foreground,
                objects=upper,
                transparent=True,
                width=canvas_w,
                height=canvas_h,
            )

            has_audio = bool(self.audio_probe(str(source)))
            command = [
                self.ffmpeg,
                "-y",
                "-loop",
                "1",
                "-i",
                str(background),
                "-i",
                str(source),
                "-loop",
                "1",
                "-i",
                str(foreground),
            ]
            if not has_audio:
                command += [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{total:.6f}",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                ]

            graph = (
                f"[0:v]scale={canvas_w}:{canvas_h},setsar=1,"
                f"trim=duration={total:.6f},setpts=PTS-STARTPTS[base];"
                f"[1:v]scale={video_w}:{video_h},setsar=1,"
                f"colorchannelmixer=aa={opacity:.6f},setpts=PTS-STARTPTS[video];"
                f"[base][video]overlay=x={x}:y={y}:eof_action=repeat:shortest=0[mid];"
                f"[2:v]scale={canvas_w}:{canvas_h},setsar=1,"
                f"trim=duration={total:.6f},setpts=PTS-STARTPTS[front];"
                f"[mid][front]overlay=x=0:y=0:eof_action=repeat:shortest=0,"
                f"trim=duration={total:.6f},fps={fps},setsar=1[outv]"
            )
            command += ["-filter_complex", graph, "-map", "[outv]"]
            if has_audio:
                command += ["-map", "1:a:0?"]
            else:
                command += ["-map", "3:a:0"]
            command += [
                "-t",
                f"{total:.6f}",
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
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            self.runner.run(command)

        return output_path
