from __future__ import annotations

import os
from dataclasses import dataclass

from .config import ProviderSettings

from .providers import (
    OpenAICompatibleAnalysisProvider,
    OpenAICompatibleTTSProvider,
    ProviderCapabilities,
    ProviderRegistry,
)


@dataclass(slots=True)
class AppServices:
    providers: ProviderRegistry


def build_services(settings: ProviderSettings | None = None) -> AppServices:
    settings = settings or ProviderSettings()
    registry = ProviderRegistry()
    ai_base = os.getenv("NOLANE_STUDIO_AI_BASE_URL") or settings.analysis_base_url
    ai_model = os.getenv("NOLANE_STUDIO_AI_MODEL") or settings.analysis_model
    api_key = os.getenv("NOLANE_STUDIO_API_KEY")
    if ai_base and ai_model:
        registry.register(
            "analysis-api",
            ProviderCapabilities(analysis=True),
            lambda: OpenAICompatibleAnalysisProvider(ai_base, api_key, ai_model),
        )

    tts_base = os.getenv("NOLANE_STUDIO_TTS_BASE_URL") or settings.tts_base_url
    tts_model = os.getenv("NOLANE_STUDIO_TTS_MODEL") or settings.tts_model
    if tts_base and tts_model:
        registry.register(
            "tts-api",
            ProviderCapabilities(tts=True),
            lambda: OpenAICompatibleTTSProvider(tts_base, api_key, tts_model),
        )
    return AppServices(registry)
