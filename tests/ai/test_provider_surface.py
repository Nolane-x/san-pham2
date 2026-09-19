from nolane_studio.providers.base import ProviderCapabilities


def test_provider_capabilities_keep_ai_project_and_ai_analyze_distinct():
    fields = ProviderCapabilities.__dataclass_fields__
    assert "analysis" in fields
    assert "vision" in fields
    assert "stt" in fields
    assert "tts" in fields
