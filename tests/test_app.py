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
