from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from nolane_studio.domain import ImageRequest, Scene, VoiceRequest


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    analysis: bool = False
    image: bool = False
    tts: bool = False
    vision: bool = False
    stt: bool = False
    clone: bool = False
    design: bool = False
    list_voices: bool = False


class AnalysisProvider(Protocol):
    def enrich(self, scenes: Sequence[Scene], instructions: str = "") -> list[Scene]: ...


class ImageProvider(Protocol):
    def generate(self, request: ImageRequest) -> bytes: ...


class TTSProvider(Protocol):
    def synthesize(self, request: VoiceRequest) -> bytes: ...


class STTProvider(Protocol):
    def transcribe_with_timestamps(
        self, audio_bytes: bytes, *, language: str | None = None
    ) -> Sequence[Any]: ...


class VisionProvider(Protocol):
    def ground_objects(
        self,
        image_bytes: bytes,
        *,
        transcript: str,
        target_phrases: Sequence[str] | None = None,
    ) -> Sequence[Any]: ...
