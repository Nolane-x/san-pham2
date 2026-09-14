from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .compositor import CompositionError, render_scene_layer_snapshot
from .exporter import build_image_segment_command, resolve_ffmpeg_exe
from .ffmpeg import SubprocessRunner
from .scene_plan import SceneRenderPlan


class UnsupportedWhiteboardMotion(CompositionError):
    """Raised when a recovered whiteboard phase cannot yet be rendered faithfully."""


@dataclass(frozen=True, slots=True)
class WhiteboardSegment:
    kind: str
    duration: float
    before_ids: tuple[str, ...]
    after_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        if kind not in {"hold", "reveal"}:
            raise ValueError("whiteboard segment kind must be hold or reveal")
        duration = float(self.duration)
        if duration <= 0:
            raise ValueError("whiteboard segment duration must be > 0")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "duration", duration)


LayerRenderer = Callable[..., Path]


def build_whiteboard_segments(plan: SceneRenderPlan) -> list[WhiteboardSegment]:
    """Translate recovered per-object timing into an additive reveal timeline.

    Pause and draw phases are represented exactly. A draw phase progressively
    wipes from the cumulative state before an object to the cumulative state
    including that object. Recovered push phases are *not* approximated as a
    hold: they fail closed until the dedicated push-motion renderer exists.
    """
    if plan.profile.style != "whiteboard":
        raise ValueError("whiteboard segments require a whiteboard render profile")

    visible = [dict(obj) for obj in plan.objects if bool(obj.get("visible", True))]
    if any(str(obj.get("kind", "")).strip().lower() == "video" for obj in visible):
        raise UnsupportedWhiteboardMotion("whiteboard source-video composition is not yet supported")

    object_ids = {str(obj.get("id", "")).strip() for obj in visible}
    timing_ids = [entry.object_id for entry in plan.object_timing]
    if any(not object_id or object_id not in object_ids for object_id in timing_ids):
        raise CompositionError("whiteboard timing references an unknown visual object")
    if set(timing_ids) != object_ids or len(timing_ids) != len(object_ids):
        raise CompositionError("whiteboard timing must cover every visible object exactly once")

    segments: list[WhiteboardSegment] = []
    revealed: list[str] = []
    cursor = 0.0
    epsilon = 1e-9

    for entry in plan.object_timing:
        if entry.push > epsilon:
            raise UnsupportedWhiteboardMotion(
                f"whiteboard object {entry.object_id} requires push motion"
            )
        if entry.start + epsilon < cursor:
            raise CompositionError("whiteboard timing overlaps previous object phase")

        implicit_gap = max(0.0, entry.start - cursor)
        current = tuple(revealed)
        if implicit_gap > epsilon:
            segments.append(WhiteboardSegment("hold", implicit_gap, current, current))
        if entry.pause > epsilon:
            segments.append(WhiteboardSegment("hold", entry.pause, current, current))

        after = tuple([*revealed, entry.object_id])
        if entry.draw > epsilon:
            segments.append(WhiteboardSegment("reveal", entry.draw, current, after))
        revealed.append(entry.object_id)
        cursor = entry.end

    remaining = float(plan.total_duration) - cursor
    if remaining < -epsilon:
        raise CompositionError("whiteboard object timing exceeds scene duration")
    if remaining > epsilon:
        final_state = tuple(revealed)
        segments.append(WhiteboardSegment("hold", remaining, final_state, final_state))
    if not segments:
        raise CompositionError("whiteboard scene has no positive-duration phases")
    return segments


def _normalize(width: int, height: int, fps: int) -> str:
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=white,"
        f"fps={max(1, int(fps))},setsar=1"
    )


def build_object_reveal_command(
    ffmpeg: str,
    before: str,
    after: str,
    output: str,
    *,
    duration: float,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    duration = float(duration)
    if duration <= 0:
        raise ValueError("reveal duration must be > 0")
    normalization = _normalize(width, height, fps)
    graph = (
        f"[0:v]{normalization},trim=duration={duration:.6f},setpts=PTS-STARTPTS[before];"
        f"[1:v]{normalization},trim=duration={duration:.6f},setpts=PTS-STARTPTS[after];"
        f"[before][after]xfade=transition=wipeleft:duration={duration:.6f}:offset=0[outv]"
    )
    return [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        before,
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        after,
        "-f",
        "lavfi",
        "-t",
        f"{duration:.6f}",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-filter_complex",
        graph,
        "-map",
        "[outv]",
        "-map",
        "2:a:0",
        "-t",
        f"{duration:.6f}",
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
        output,
    ]


def _concat_escape(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "'\\''")


class WhiteboardSceneCompositor:
    """Render standard whiteboard scenes object-by-object with bounded memory."""

    def __init__(
        self,
        *,
        ffmpeg: str | None = None,
        runner: SubprocessRunner | None = None,
        layer_renderer: LayerRenderer = render_scene_layer_snapshot,
    ) -> None:
        self.ffmpeg = ffmpeg or resolve_ffmpeg_exe()
        self.runner = runner or SubprocessRunner()
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
        segments = build_whiteboard_segments(plan)
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        objects_by_id: Mapping[str, Mapping[str, object]] = {
            str(obj.get("id", "")): obj
            for obj in plan.objects
            if bool(obj.get("visible", True))
        }

        with tempfile.TemporaryDirectory(prefix="nolane-studio-whiteboard-") as temp_raw:
            temp = Path(temp_raw)
            state_paths: dict[tuple[str, ...], Path] = {}

            def ensure_state(state: tuple[str, ...]) -> Path:
                existing = state_paths.get(state)
                if existing is not None:
                    return existing
                path = temp / f"state-{len(state_paths):04d}.png"
                objects: Sequence[Mapping[str, object]] = [objects_by_id[object_id] for object_id in state]
                rendered = Path(
                    self.layer_renderer(
                        plan,
                        path,
                        objects=objects,
                        transparent=False,
                        width=width,
                        height=height,
                    )
                )
                state_paths[state] = rendered
                return rendered

            # Resolve states in first-use order so the compositor stays
            # deterministic and tests can verify the cumulative reveal model.
            for segment in segments:
                ensure_state(segment.before_ids)
                ensure_state(segment.after_ids)

            media_segments: list[Path] = []
            for index, segment in enumerate(segments):
                target = temp / f"segment-{index:04d}.mp4"
                before = ensure_state(segment.before_ids)
                after = ensure_state(segment.after_ids)
                if segment.kind == "hold":
                    command = build_image_segment_command(
                        self.ffmpeg,
                        str(after),
                        str(target),
                        duration=segment.duration,
                        width=width,
                        height=height,
                        fps=fps,
                    )
                else:
                    command = build_object_reveal_command(
                        self.ffmpeg,
                        str(before),
                        str(after),
                        str(target),
                        duration=segment.duration,
                        width=width,
                        height=height,
                        fps=fps,
                    )
                self.runner.run(command)
                media_segments.append(target)

            concat_file = temp / "concat.txt"
            concat_file.write_text(
                "".join(f"file '{_concat_escape(segment)}'\n" for segment in media_segments),
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
                    str(output_path),
                ]
            )
        return output_path
