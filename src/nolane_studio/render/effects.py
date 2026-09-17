from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .config import InvalidSceneDuration, normalize_render_config


class InvalidObjectTiming(ValueError):
    """Raised when persisted object timing cannot form a finite timeline."""


@dataclass(frozen=True, slots=True)
class RenderProfile:
    style: str = "static"
    camera: str = "static"
    reveal_duration: float = 0.0
    hold_duration: float = 6.0

    def __post_init__(self) -> None:
        style = str(self.style).strip().lower().replace("-", "_")
        camera = str(self.camera).strip().lower().replace("-", "_")
        if style not in {"static", "whiteboard", "color_reveal"}:
            raise ValueError("style must be static, whiteboard, or color_reveal")
        if camera not in {"static", "slow_zoom", "pan_left", "pan_right"}:
            raise ValueError("camera must be static, slow_zoom, pan_left, or pan_right")
        reveal = float(self.reveal_duration)
        hold = float(self.hold_duration)
        for field, value in (("reveal_duration", reveal), ("hold_duration", hold)):
            if not math.isfinite(value):
                raise InvalidSceneDuration(f"render profile {field} must be finite")
        total = reveal + hold
        if not math.isfinite(total):
            raise InvalidSceneDuration("render profile total duration must be finite")
        if reveal < 0 or hold < 0 or total <= 0:
            raise ValueError("render profile requires a positive total duration")
        object.__setattr__(self, "style", style)
        object.__setattr__(self, "camera", camera)
        object.__setattr__(self, "reveal_duration", reveal)
        object.__setattr__(self, "hold_duration", hold)

    @property
    def total_duration(self) -> float:
        return self.reveal_duration + self.hold_duration


@dataclass(frozen=True, slots=True)
class ObjectTimingEntry:
    object_id: str
    start: float
    pause: float
    draw: float
    push: float

    def __post_init__(self) -> None:
        object_id = str(self.object_id).strip()
        if not object_id:
            raise ValueError("object_id must not be blank")
        fields = (
            ("start", float(self.start)),
            ("pause", float(self.pause)),
            ("draw", float(self.draw)),
            ("push", float(self.push)),
        )
        for field, value in fields:
            if not math.isfinite(value):
                raise InvalidObjectTiming(
                    f"object {object_id} timing {field} must be finite"
                )
        values = tuple(value for _field, value in fields)
        if any(value < 0 for value in values):
            raise ValueError("object timing values must be >= 0")
        if not math.isfinite(sum(values)):
            raise InvalidObjectTiming(
                f"object {object_id} timing total must be finite"
            )
        object.__setattr__(self, "object_id", object_id)
        object.__setattr__(self, "start", values[0])
        object.__setattr__(self, "pause", values[1])
        object.__setattr__(self, "draw", values[2])
        object.__setattr__(self, "push", values[3])

    @property
    def end(self) -> float:
        return self.start + self.pause + self.draw + self.push


def _nonnegative_seconds(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    return max(0.0, number)


def _finite_nonnegative_seconds(
    value: Any,
    *,
    field: str,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)
    if not math.isfinite(number):
        raise InvalidSceneDuration(f"{field} must be finite")
    return max(0.0, number)


def _timing_value(raw: Mapping[str, Any], name: str, default: float) -> float:
    for key in (name, f"{name}_seconds", f"{name}_duration"):
        if key in raw:
            try:
                number = float(raw.get(key))
            except (TypeError, ValueError):
                return _nonnegative_seconds(default)
            if not math.isfinite(number):
                raise InvalidObjectTiming(f"timing {name} must be finite")
            return max(0.0, number)
    return _nonnegative_seconds(default)


def _camera_action(raw: Mapping[str, Any]) -> str:
    config = normalize_render_config(raw)
    if config["visual_mode"] != "camera_motion":
        return "static"

    candidates: list[Mapping[str, Any]] = []
    custom = config.get("custom_camera_config") or []
    if isinstance(custom, list):
        candidates.extend(item for item in custom if isinstance(item, Mapping))
    image_motion = config.get("image_motion_config") or {}
    if isinstance(image_motion, Mapping):
        candidates.append(image_motion)

    action = ""
    for candidate in candidates:
        value = candidate.get("action") or candidate.get("mode") or candidate.get("type")
        if value:
            action = str(value).strip().lower().replace("-", "_")
            break

    if action in {"pan_left", "left", "move_left"}:
        return "pan_left"
    if action in {"pan_right", "right", "move_right"}:
        return "pan_right"
    if action in {"static", "none", "off"}:
        return "static"
    return "slow_zoom"


def render_profile_from_config(raw: Mapping[str, Any] | None) -> RenderProfile:
    config = normalize_render_config(raw)
    return RenderProfile(
        style=config["style"],
        camera=_camera_action(config),
        reveal_duration=float(config["reveal_duration"]),
        hold_duration=float(config["hold_duration"]),
    )


def build_render_timing_plan(
    objects: Sequence[Mapping[str, Any]],
    raw_config: Mapping[str, Any] | None,
) -> list[ObjectTimingEntry]:
    """Build the recovered sequential object timing plan.

    The original engine exposes per-object ``pause / draw / push`` timing.
    Fixed mode preserves the scene reveal duration by distributing drawing
    time over visible objects. Custom mode applies explicit per-object phases
    in visual-object order and falls back to the fixed share for missing draw
    entries so incomplete saved configs remain renderable.
    """
    config = normalize_render_config(raw_config)
    visible = [obj for obj in objects if bool(obj.get("visible", True)) and str(obj.get("id", "")).strip()]
    if not visible:
        return []

    reveal = _nonnegative_seconds(config.get("reveal_duration"), 0.0)
    fixed_draw = reveal / len(visible)
    mode = str(config.get("object_timing_mode", "fixed") or "fixed").strip().lower()

    custom_by_id: dict[str, Mapping[str, Any]] = {}
    if mode == "custom":
        custom = config.get("custom_object_timing_config") or []
        if isinstance(custom, list):
            for entry in custom:
                if not isinstance(entry, Mapping):
                    continue
                object_id = str(entry.get("object_id") or entry.get("id") or "").strip()
                if object_id and object_id not in custom_by_id:
                    custom_by_id[object_id] = entry

    plan: list[ObjectTimingEntry] = []
    cursor = 0.0
    for obj in visible:
        object_id = str(obj["id"]).strip()
        custom = custom_by_id.get(object_id) if mode == "custom" else None
        try:
            pause = _timing_value(custom, "pause", 0.0) if custom is not None else 0.0
            draw = _timing_value(custom, "draw", fixed_draw) if custom is not None else fixed_draw
            push = _timing_value(custom, "push", 0.0) if custom is not None else 0.0
        except InvalidObjectTiming as exc:
            raise InvalidObjectTiming(f"object {object_id} {exc}") from exc
        entry = ObjectTimingEntry(object_id=object_id, start=cursor, pause=pause, draw=draw, push=push)
        plan.append(entry)
        cursor = entry.end
    return plan


def estimate_object_timeline_seconds(
    plan: Sequence[ObjectTimingEntry],
    *,
    hold_duration: float = 0.0,
    outro_duration: float = 0.0,
) -> float:
    object_end = max((entry.end for entry in plan), default=0.0)
    hold = _finite_nonnegative_seconds(hold_duration, field="hold_duration")
    outro = _finite_nonnegative_seconds(outro_duration, field="outro_duration")
    total = object_end + hold + outro
    if not math.isfinite(total):
        raise InvalidSceneDuration("scene timeline total duration must be finite")
    return total


def _normalization(width: int, height: int, fps: int) -> str:
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


def _camera_filter(width: int, height: int, fps: int, camera: str) -> str:
    if camera == "static":
        return ""
    if camera == "slow_zoom":
        return (
            f",zoompan=z='min(zoom+0.0008,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    if camera == "pan_left":
        return (
            f",zoompan=z='1.05':x='max(0,(iw-iw/zoom)*(1-on/(fps*8)))':"
            f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"
        )
    return (
        f",zoompan=z='1.05':x='min(iw-iw/zoom,(iw-iw/zoom)*(on/(fps*8)))':"
        f"y='ih/2-(ih/zoom/2)':d=1:s={width}x{height}:fps={fps}"
    )


def build_camera_filter_chain(width: int, height: int, fps: int, camera: str) -> str:
    """Return the shared normalization + recovered camera-motion filter chain."""
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    fps = max(1, int(fps))
    camera = str(camera).strip().lower().replace("-", "_")
    if camera not in {"static", "slow_zoom", "pan_left", "pan_right"}:
        raise ValueError("camera must be static, slow_zoom, pan_left, or pan_right")
    return _normalization(width, height, fps) + _camera_filter(width, height, fps, camera)


def build_image_filter_graph(
    width: int,
    height: int,
    fps: int,
    profile: RenderProfile,
    *,
    total_duration: float | None = None,
) -> str:
    """Build a single-output FFmpeg filter graph labeled ``[outv]``.

    ``total_duration`` is authoritative when supplied. This keeps recovered
    object timing (pause/draw/push/outro) independent from the visual reveal
    profile while preserving the existing profile-only behavior for callers
    that do not have a scene timeline.
    """
    width = max(2, int(width))
    height = max(2, int(height))
    if width % 2:
        width -= 1
    if height % 2:
        height -= 1
    fps = max(1, int(fps))
    total = profile.total_duration if total_duration is None else float(total_duration)
    if not math.isfinite(total):
        raise ValueError("total_duration must be finite")
    if total <= 0:
        raise ValueError("total_duration must be > 0")
    reveal = min(profile.reveal_duration, total)
    base = build_camera_filter_chain(width, height, fps, profile.camera)

    if profile.style == "static" or reveal <= 0:
        return f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS[outv]"

    if profile.style == "whiteboard":
        return (
            f"color=c=white:s={width}x{height}:r={fps}:d={total:.6f}[white];"
            f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS,fps={fps}[image];"
            f"[white][image]xfade=transition=wipeleft:duration={reveal:.6f}:offset=0[outv]"
        )

    return (
        f"[0:v]{base},trim=duration={total:.6f},setpts=PTS-STARTPTS,fps={fps},split=2[gray_src][color_src];"
        f"[gray_src]hue=s=0[gray];"
        f"[gray][color_src]xfade=transition=wipeleft:duration={reveal:.6f}:offset=0[outv]"
    )
