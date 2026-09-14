from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .compositor import CompositionError, render_scene_layer_snapshot
from .effects import build_camera_filter_chain
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
    object_id: str | None = None
    direction: str | None = None

    def __post_init__(self) -> None:
        kind = str(self.kind).strip().lower()
        if kind not in {"hold", "reveal", "push", "outro"}:
            raise ValueError("whiteboard segment kind must be hold, reveal, push, or outro")
        duration = float(self.duration)
        if duration <= 0:
            raise ValueError("whiteboard segment duration must be > 0")
        object_id = None if self.object_id is None else str(self.object_id).strip()
        direction = None if self.direction is None else str(self.direction).strip().lower().replace("-", "_")
        if kind == "push" and (not object_id or not direction):
            raise ValueError("push segment requires object_id and direction")
        if kind == "outro" and not direction:
            raise ValueError("outro segment requires direction")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "duration", duration)
        object.__setattr__(self, "object_id", object_id)
        object.__setattr__(self, "direction", direction)


LayerRenderer = Callable[..., Path]


def _push_direction(plan: SceneRenderPlan) -> str:
    value = plan.render_config.get("large_object_push_direction", "from_left")
    direction = str(value or "from_left").strip().lower().replace("-", "_")
    # ``from_left`` is the recovered default and is the only direction whose
    # behavior is currently backed strongly enough to render instead of guess.
    if direction != "from_left":
        raise UnsupportedWhiteboardMotion(f"unsupported whiteboard push direction: {direction}")
    return direction


def _outro_direction(plan: SceneRenderPlan) -> str:
    value = plan.render_config.get("outro_direction", "left")
    direction = str(value or "left").strip().lower().replace("-", "_")
    # ``left`` is the recovered/default exit direction. Other directions stay
    # fail-closed until their native behavior is evidenced strongly enough.
    if direction != "left":
        raise UnsupportedWhiteboardMotion(f"unsupported whiteboard outro direction: {direction}")
    return direction


def _outro_duration(plan: SceneRenderPlan) -> float:
    if not bool(plan.render_config.get("outro_enabled", False)):
        return 0.0
    try:
        return max(0.0, float(plan.render_config.get("outro_duration", 0.0)))
    except (TypeError, ValueError):
        return 0.0


def build_whiteboard_segments(plan: SceneRenderPlan) -> list[WhiteboardSegment]:
    """Translate recovered per-object timing into an additive whiteboard timeline.

    Pause and draw phases remain exact additive phases. The recovered default
    object-push direction (``from_left``) is represented as a dedicated motion
    phase after the object's reveal and before the next object's timing begins.
    A configured recovered outro remains a distinct additive exit phase after
    the final hold instead of being flattened into static time. Directions whose
    original native-engine behavior has not been recovered strongly enough fail
    closed rather than being approximated.
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

        if entry.push > epsilon:
            direction = _push_direction(plan)
            persisted = tuple(revealed)
            segments.append(
                WhiteboardSegment(
                    "push",
                    entry.push,
                    persisted,
                    persisted,
                    object_id=entry.object_id,
                    direction=direction,
                )
            )
        cursor = entry.end

    remaining = float(plan.total_duration) - cursor
    if remaining < -epsilon:
        raise CompositionError("whiteboard object timing exceeds scene duration")

    final_state = tuple(revealed)
    outro = _outro_duration(plan)
    if outro > remaining + epsilon:
        raise CompositionError("whiteboard outro duration exceeds remaining scene duration")
    hold_remaining = max(0.0, remaining - outro)
    if hold_remaining > epsilon:
        segments.append(WhiteboardSegment("hold", hold_remaining, final_state, final_state))
    if outro > epsilon:
        segments.append(
            WhiteboardSegment(
                "outro",
                outro,
                final_state,
                final_state,
                direction=_outro_direction(plan),
            )
        )
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


def build_object_push_command(
    ffmpeg: str,
    base: str,
    object_layer: str,
    output: str,
    *,
    duration: float,
    direction: str,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    """Build the behaviorally recovered from-left object-entry/push segment.

    The old native engine exposes direction/config, movement and persistence,
    but not source-exact motion equations. We therefore implement only the
    recovered default ``from_left`` contract: the isolated object layer moves
    from outside the left canvas edge to its persisted editor geometry while
    all previously revealed objects remain fixed.
    """
    duration = float(duration)
    if duration <= 0:
        raise ValueError("push duration must be > 0")
    direction = str(direction).strip().lower().replace("-", "_")
    if direction != "from_left":
        raise UnsupportedWhiteboardMotion(f"unsupported whiteboard push direction: {direction}")

    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    fps = max(1, int(fps))
    normalization = _normalize(width, height, fps)
    x_expression = f"-{width}+{width}*min(t/{duration:.6f},1)"
    graph = (
        f"[0:v]{normalization},trim=duration={duration:.6f},setpts=PTS-STARTPTS[base];"
        f"[1:v]scale={width}:{height},format=rgba,fps={fps},setsar=1,"
        f"trim=duration={duration:.6f},setpts=PTS-STARTPTS[object];"
        f"[base][object]overlay=x='{x_expression}':y=0:eval=frame:shortest=1[outv]"
    )
    return [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        base,
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        object_layer,
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


def build_scene_outro_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    duration: float,
    direction: str,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    """Move the fully revealed whiteboard canvas out in the recovered left outro."""
    duration = float(duration)
    if duration <= 0:
        raise ValueError("outro duration must be > 0")
    direction = str(direction).strip().lower().replace("-", "_")
    if direction != "left":
        raise UnsupportedWhiteboardMotion(f"unsupported whiteboard outro direction: {direction}")

    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    fps = max(1, int(fps))
    normalization = _normalize(width, height, fps)
    x_expression = f"-{width}*min(t/{duration:.6f},1)"
    graph = (
        f"[0:v]{normalization},format=rgba,trim=duration={duration:.6f},setpts=PTS-STARTPTS[scene];"
        f"[1:v]format=rgba,trim=duration={duration:.6f},setpts=PTS-STARTPTS[background];"
        f"[background][scene]overlay=x='{x_expression}':y=0:eval=frame:shortest=1[outv]"
    )
    return [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.6f}",
        "-i",
        source,
        "-f",
        "lavfi",
        "-t",
        f"{duration:.6f}",
        "-i",
        f"color=c=white:s={width}x{height}:r={fps}",
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


def build_scene_camera_command(
    ffmpeg: str,
    source: str,
    output: str,
    *,
    camera: str,
    duration: float,
    width: int = 1280,
    height: int = 720,
    fps: int = 24,
) -> list[str]:
    """Apply recovered camera motion after object timing has been rendered."""
    duration = float(duration)
    if duration <= 0:
        raise ValueError("camera duration must be > 0")
    camera = str(camera).strip().lower().replace("-", "_")
    if camera == "static":
        raise ValueError("static camera does not require a postprocess command")
    video_filter = build_camera_filter_chain(width, height, fps, camera)
    return [
        ffmpeg,
        "-y",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        video_filter,
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
        "copy",
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
            object_layer_paths: dict[str, Path] = {}

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

            def ensure_object_layer(object_id: str) -> Path:
                existing = object_layer_paths.get(object_id)
                if existing is not None:
                    return existing
                path = temp / f"object-{len(object_layer_paths):04d}-{object_id}.png"
                rendered = Path(
                    self.layer_renderer(
                        plan,
                        path,
                        objects=[objects_by_id[object_id]],
                        transparent=True,
                        width=width,
                        height=height,
                    )
                )
                object_layer_paths[object_id] = rendered
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
                elif segment.kind == "reveal":
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
                elif segment.kind == "push":
                    assert segment.object_id is not None and segment.direction is not None
                    base_ids = tuple(object_id for object_id in segment.after_ids if object_id != segment.object_id)
                    base = ensure_state(base_ids)
                    object_layer = ensure_object_layer(segment.object_id)
                    command = build_object_push_command(
                        self.ffmpeg,
                        str(base),
                        str(object_layer),
                        str(target),
                        duration=segment.duration,
                        direction=segment.direction,
                        width=width,
                        height=height,
                        fps=fps,
                    )
                else:
                    assert segment.direction is not None
                    command = build_scene_outro_command(
                        self.ffmpeg,
                        str(after),
                        str(target),
                        duration=segment.duration,
                        direction=segment.direction,
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
            camera = plan.profile.camera
            concat_output = (
                output_path
                if camera == "static"
                else temp / f"{output_path.stem}-pre-camera.mp4"
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
                    str(concat_output),
                ]
            )
            if camera != "static":
                self.runner.run(
                    build_scene_camera_command(
                        self.ffmpeg,
                        str(concat_output),
                        str(output_path),
                        camera=camera,
                        duration=plan.total_duration,
                        width=width,
                        height=height,
                        fps=fps,
                    )
                )
        return output_path