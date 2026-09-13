from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _non_blank(value: str, field_name: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{field_name} must not be blank")
    return value


def _non_negative(value: float, field_name: str) -> float:
    value = float(value)
    if value < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return value


@dataclass(frozen=True, slots=True)
class Scene:
    index: int
    text: str
    image_prompt: str = ""
    voice_text: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index must be >= 0")
        object.__setattr__(self, "text", _non_blank(self.text, "text"))
        if not self.voice_text:
            object.__setattr__(self, "voice_text", self.text)


@dataclass(frozen=True, slots=True)
class ProjectSpec:
    project_id: str
    title: str
    output_w: int = 1280
    output_h: int = 720
    fps: int = 24

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_id", _non_blank(self.project_id, "project_id"))
        object.__setattr__(self, "title", _non_blank(self.title, "title"))
        if self.output_w <= 0 or self.output_h <= 0:
            raise ValueError("output dimensions must be positive")
        if self.output_w % 2 or self.output_h % 2:
            raise ValueError("output dimensions must be even for H.264 compatibility")
        if self.fps <= 0:
            raise ValueError("fps must be positive")


@dataclass(frozen=True, slots=True)
class RenderConfig:
    style: str = "whiteboard"
    visual_mode: str = "drawing"
    reveal_duration: float = 8.0
    hold_duration: float = 1.0
    brush_mode: str = "lr"
    hand_style: str = "hand-1.png"
    remove_background_enabled: bool = False
    outro_enabled: bool = False
    outro_direction: str = "left"
    outro_duration: float = 0.3
    extras: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reveal_duration", _non_negative(self.reveal_duration, "reveal_duration"))
        object.__setattr__(self, "hold_duration", _non_negative(self.hold_duration, "hold_duration"))
        object.__setattr__(self, "outro_duration", _non_negative(self.outro_duration, "outro_duration"))


@dataclass(frozen=True, slots=True)
class TransitionSpec:
    from_id: str
    to_id: str
    effect: str
    duration: float
    settings: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_id", _non_blank(self.from_id, "from_id"))
        object.__setattr__(self, "to_id", _non_blank(self.to_id, "to_id"))
        object.__setattr__(self, "effect", _non_blank(self.effect, "effect"))
        duration = float(self.duration)
        if not 0.1 <= duration <= 10.0:
            raise ValueError("transition duration must be within 0.1..10 seconds")
        object.__setattr__(self, "duration", duration)


@dataclass(frozen=True, slots=True)
class VoiceRequest:
    text: str
    language: str = "vi-VN"
    voice: str | None = None
    reference_audio: str | None = None
    reference_text: str | None = None
    design_instructions: str | None = None
    speed: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "text", _non_blank(self.text, "text"))
        object.__setattr__(self, "language", _non_blank(self.language, "language"))
        if self.speed <= 0:
            raise ValueError("speed must be > 0")
