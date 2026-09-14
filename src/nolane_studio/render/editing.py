from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping


def _positive(value: float, name: str) -> float:
    value = float(value)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


@dataclass(frozen=True, slots=True)
class TimelineClip:
    clip_id: str
    path: str
    kind: str
    source_duration: float | None = None
    still_duration: float = 6.0
    trim_start: float = 0.0
    trim_end: float | None = None
    speed: float = 1.0
    render_profile: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clip_id = str(self.clip_id).strip()
        path = str(self.path).strip()
        kind = str(self.kind).strip().lower()
        if not clip_id:
            raise ValueError("clip_id must not be blank")
        if not path:
            raise ValueError("path must not be blank")
        if kind not in {"image", "video"}:
            raise ValueError("kind must be image or video")
        speed = _positive(self.speed, "speed")
        trim_start = float(self.trim_start)
        if trim_start < 0:
            raise ValueError("trim_start must be >= 0")

        object.__setattr__(self, "clip_id", clip_id)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "speed", speed)
        object.__setattr__(self, "trim_start", trim_start)
        object.__setattr__(self, "render_profile", dict(self.render_profile))

        if kind == "image":
            object.__setattr__(self, "still_duration", _positive(self.still_duration, "still_duration"))
            object.__setattr__(self, "source_duration", None)
            object.__setattr__(self, "trim_start", 0.0)
            object.__setattr__(self, "trim_end", None)
            return

        if self.source_duration is None:
            raise ValueError("video source_duration is required")
        source_duration = _positive(self.source_duration, "source_duration")
        trim_end = source_duration if self.trim_end is None else float(self.trim_end)
        if trim_end <= trim_start:
            raise ValueError("trim_end must be greater than trim_start")
        if trim_end > source_duration:
            raise ValueError("trim_end must not exceed source_duration")
        if trim_start >= source_duration:
            raise ValueError("trim_start must be before source_duration")
        object.__setattr__(self, "source_duration", source_duration)
        object.__setattr__(self, "trim_end", trim_end)

    @property
    def effective_duration(self) -> float:
        if self.kind == "image":
            return self.still_duration
        assert self.trim_end is not None
        return (self.trim_end - self.trim_start) / self.speed

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["render_profile"] = dict(self.render_profile)
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TimelineClip":
        return cls(
            clip_id=str(raw["clip_id"]),
            path=str(raw["path"]),
            kind=str(raw["kind"]),
            source_duration=raw.get("source_duration"),
            still_duration=raw.get("still_duration", 6.0),
            trim_start=raw.get("trim_start", 0.0),
            trim_end=raw.get("trim_end"),
            speed=raw.get("speed", 1.0),
            render_profile=raw.get("render_profile") or {},
        )


def split_clip(clip: TimelineClip, at: float) -> tuple[TimelineClip, TimelineClip]:
    at = float(at)
    if at <= 0 or at >= clip.effective_duration:
        raise ValueError("split point must be inside the clip")

    if clip.kind == "image":
        left = replace(clip, clip_id=f"{clip.clip_id}-a", still_duration=at)
        right = replace(
            clip,
            clip_id=f"{clip.clip_id}-b",
            still_duration=clip.effective_duration - at,
        )
        return left, right

    source_split = clip.trim_start + at * clip.speed
    left = replace(clip, clip_id=f"{clip.clip_id}-a", trim_end=source_split)
    right = replace(clip, clip_id=f"{clip.clip_id}-b", trim_start=source_split)
    return left, right
