from __future__ import annotations

from nolane_studio.app import build_services
from nolane_studio.config import ProviderSettings


def test_persisted_image_settings_register_lazy_image_provider():
    services = build_services(
        ProviderSettings(
            image_base_url="https://images.example/v1",
            image_model="image-model",
        )
    )

    matches = services.providers.find(image=True)
    assert [item.name for item in matches] == ["image-api"]
    assert services.providers.describe("image-api").capabilities.image is True


def test_image_environment_overrides_register_provider(monkeypatch):
    monkeypatch.setenv("NOLANE_STUDIO_IMAGE_BASE_URL", "https://env-images.example/v1")
    monkeypatch.setenv("NOLANE_STUDIO_IMAGE_MODEL", "env-image-model")

    services = build_services()

    assert [item.name for item in services.providers.find(image=True)] == ["image-api"]
