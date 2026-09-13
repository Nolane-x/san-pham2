from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from nolane_studio.domain import Scene, VoiceRequest


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    analysis: bool = False
    tts: bool = False
    clone: bool = False
    design: bool = False
    list_voices: bool = False


class AnalysisProvider(Protocol):
    def enrich(self, scenes: Sequence[Scene], instructions: str = "") -> list[Scene]: ...


class TTSProvider(Protocol):
    def synthesize(self, request: VoiceRequest) -> bytes: ...
