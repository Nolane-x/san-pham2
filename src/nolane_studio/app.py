from __future__ import annotations

import os
from dataclasses import dataclass

from .config import ProviderSettings

from .providers import (
    OpenAICompatibleAnalysisProvider,
    OpenAICompatibleImageProvider,
    OpenAICompatibleSTTProvider,
    OpenAICompatibleTTSProvider,
    OpenAICompatibleVisionProvider,
    ProviderCapabilities,
    ProviderRegistry,
)


@dataclass(slots=True)
class AppServices:
    providers: ProviderRegistry


def build_services(settings: ProviderSettings | None = None) -> AppServices:
    settings = settings or ProviderSettings()
    registry = ProviderRegistry()
    api_key = os.getenv("NOLANE_STUDIO_API_KEY")

    ai_base = os.getenv("NOLANE_STUDIO_AI_BASE_URL") or settings.analysis_base_url
    ai_model = os.getenv("NOLANE_STUDIO_AI_MODEL") or settings.analysis_model
    if ai_base and ai_model:
        registry.register(
            "analysis-api",
            ProviderCapabilities(analysis=True),
            lambda: OpenAICompatibleAnalysisProvider(ai_base, api_key, ai_model),
        )

    image_base = os.getenv("NOLANE_STUDIO_IMAGE_BASE_URL") or settings.image_base_url
    image_model = os.getenv("NOLANE_STUDIO_IMAGE_MODEL") or settings.image_model
    if image_base and image_model:
        registry.register(
            "image-api",
            ProviderCapabilities(image=True),
            lambda: OpenAICompatibleImageProvider(
                image_base,
                api_key,
                image_model,
            ),
        )

    vision_base = os.getenv("NOLANE_STUDIO_VISION_BASE_URL") or settings.vision_base_url
    vision_model = os.getenv("NOLANE_STUDIO_VISION_MODEL") or settings.vision_model
    if vision_base and vision_model:
        registry.register(
            "vision-api",
            ProviderCapabilities(vision=True),
            lambda: OpenAICompatibleVisionProvider(
                vision_base,
                api_key,
                vision_model,
            ),
        )

    stt_base = os.getenv("NOLANE_STUDIO_STT_BASE_URL") or settings.stt_base_url
    stt_model = os.getenv("NOLANE_STUDIO_STT_MODEL") or settings.stt_model
    if stt_base and stt_model:
        registry.register(
            "stt-api",
            ProviderCapabilities(stt=True),
            lambda: OpenAICompatibleSTTProvider(
                stt_base,
                api_key,
                stt_model,
            ),
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
