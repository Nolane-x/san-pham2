from nolane_studio.config import ProviderSettings
from nolane_studio.providers.base import ProviderCapabilities


def test_provider_contract_exposes_api_first_stt_and_vision_capabilities():
    assert "vision_base_url" in ProviderSettings.__dataclass_fields__
    assert "vision_model" in ProviderSettings.__dataclass_fields__
    assert "stt_base_url" in ProviderSettings.__dataclass_fields__
    assert "stt_model" in ProviderSettings.__dataclass_fields__
    assert "vision" in ProviderCapabilities.__dataclass_fields__
    assert "stt" in ProviderCapabilities.__dataclass_fields__
