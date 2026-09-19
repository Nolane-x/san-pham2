from nolane_studio.app import build_services
from nolane_studio.config import ProviderSettings


def test_build_services_uses_persisted_provider_settings(monkeypatch):
    for key in [
        "NOLANE_STUDIO_AI_BASE_URL", "NOLANE_STUDIO_AI_MODEL",
        "NOLANE_STUDIO_TTS_BASE_URL", "NOLANE_STUDIO_TTS_MODEL",
        "NOLANE_STUDIO_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    services = build_services(
        ProviderSettings(
            analysis_base_url="https://analysis.example/v1",
            analysis_model="analysis-model",
            tts_base_url="https://voice.example/v1",
            tts_model="voice-model",
        )
    )
    names = [descriptor.name for descriptor in services.providers.descriptors()]
    assert names == ["analysis-api", "tts-api"]

def test_build_services_registers_vision_and_stt_from_persisted_settings(monkeypatch):
    for key in [
        "NOLANE_STUDIO_AI_BASE_URL",
        "NOLANE_STUDIO_AI_MODEL",
        "NOLANE_STUDIO_VISION_BASE_URL",
        "NOLANE_STUDIO_VISION_MODEL",
        "NOLANE_STUDIO_STT_BASE_URL",
        "NOLANE_STUDIO_STT_MODEL",
        "NOLANE_STUDIO_TTS_BASE_URL",
        "NOLANE_STUDIO_TTS_MODEL",
        "NOLANE_STUDIO_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    services = build_services(
        ProviderSettings(
            vision_base_url="https://vision.example/v1",
            vision_model="vision-model",
            stt_base_url="https://stt.example/v1",
            stt_model="stt-model",
        )
    )

    descriptors = {item.name: item.capabilities for item in services.providers.descriptors()}
    assert descriptors["vision-api"].vision is True
    assert descriptors["stt-api"].stt is True
    assert services.providers.get("vision-api").model == "vision-model"
    assert services.providers.get("stt-api").model == "stt-model"


def test_build_services_vision_and_stt_environment_override_persisted_settings(monkeypatch):
    monkeypatch.delenv("NOLANE_STUDIO_AI_BASE_URL", raising=False)
    monkeypatch.delenv("NOLANE_STUDIO_AI_MODEL", raising=False)
    monkeypatch.delenv("NOLANE_STUDIO_TTS_BASE_URL", raising=False)
    monkeypatch.delenv("NOLANE_STUDIO_TTS_MODEL", raising=False)
    monkeypatch.setenv("NOLANE_STUDIO_VISION_BASE_URL", "https://env-vision.example/v1")
    monkeypatch.setenv("NOLANE_STUDIO_VISION_MODEL", "env-vision")
    monkeypatch.setenv("NOLANE_STUDIO_STT_BASE_URL", "https://env-stt.example/v1")
    monkeypatch.setenv("NOLANE_STUDIO_STT_MODEL", "env-stt")

    services = build_services(
        ProviderSettings(
            vision_base_url="https://saved-vision.example/v1",
            vision_model="saved-vision",
            stt_base_url="https://saved-stt.example/v1",
            stt_model="saved-stt",
        )
    )

    vision = services.providers.get("vision-api")
    stt = services.providers.get("stt-api")
    assert (vision.base_url, vision.model) == ("https://env-vision.example/v1", "env-vision")
    assert (stt.base_url, stt.model) == ("https://env-stt.example/v1", "env-stt")

