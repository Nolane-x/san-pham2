from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nolane_studio.app import build_services
from nolane_studio.config import ProviderSettings, SettingsStore
from nolane_studio.providers import GenericHttpTTSProvider
from nolane_studio.providers.http import HttpResponse


class FakeCatalogTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response
        self.calls: list[dict] = []

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        json_body=None,
        body=None,
        timeout=60.0,
    ):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers or {},
                "json_body": json_body,
                "body": body,
                "timeout": timeout,
            }
        )
        return self.response


def test_build_services_registers_configured_advanced_voice_http_adapter(monkeypatch):
    for key in (
        "NOLANE_STUDIO_TTS_BASE_URL",
        "NOLANE_STUDIO_TTS_MODEL",
        "NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT",
        "NOLANE_STUDIO_TTS_VOICES_ENDPOINT",
        "NOLANE_STUDIO_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    services = build_services(
        ProviderSettings(
            tts_advanced_endpoint="https://voice.example/tts",
            tts_voices_endpoint="https://voice.example/voices",
        )
    )

    descriptor = next(item for item in services.providers.descriptors() if item.name == "tts-api")
    assert descriptor.capabilities.tts is True
    assert descriptor.capabilities.clone is True
    assert descriptor.capabilities.design is True
    assert descriptor.capabilities.list_voices is True

    provider = services.providers.get("tts-api")
    assert isinstance(provider, GenericHttpTTSProvider)
    assert provider.endpoint == "https://voice.example/tts"
    assert provider.voices_endpoint == "https://voice.example/voices"


def test_advanced_voice_environment_overrides_saved_endpoints(monkeypatch):
    monkeypatch.setenv("NOLANE_STUDIO_TTS_ADVANCED_ENDPOINT", "https://env.example/tts")
    monkeypatch.setenv("NOLANE_STUDIO_TTS_VOICES_ENDPOINT", "https://env.example/voices")

    services = build_services(
        ProviderSettings(
            tts_advanced_endpoint="https://saved.example/tts",
            tts_voices_endpoint="https://saved.example/voices",
        )
    )

    provider = services.providers.get("tts-api")
    assert provider.endpoint == "https://env.example/tts"
    assert provider.voices_endpoint == "https://env.example/voices"


def test_generic_advanced_voice_adapter_discovers_catalog_from_explicit_endpoint():
    transport = FakeCatalogTransport(
        HttpResponse(
            200,
            {"content-type": "application/json"},
            json.dumps({"voices": ["teacher", "narrator", "teacher"]}).encode(),
        )
    )
    provider = GenericHttpTTSProvider(
        "https://voice.example/tts",
        voices_endpoint="https://voice.example/voices",
        headers={"Authorization": "Bearer secret"},
        transport=transport,
    )

    assert provider.list_voices() == ["teacher", "narrator"]
    assert transport.calls == [
        {
            "method": "GET",
            "url": "https://voice.example/voices",
            "headers": {"Authorization": "Bearer secret"},
            "json_body": None,
            "body": None,
            "timeout": 60.0,
        }
    ]


def test_generic_advanced_voice_adapter_fails_closed_without_catalog_endpoint():
    provider = GenericHttpTTSProvider("https://voice.example/tts")

    with pytest.raises(RuntimeError, match="voice catalog"):
        provider.list_voices()


def test_providers_page_persists_advanced_voice_endpoints(tmp_path):
    from PySide6.QtWidgets import QApplication

    from nolane_studio.ui.pages_base import ProvidersPage

    QApplication.instance() or QApplication([])
    settings_store = SettingsStore(tmp_path / "settings.json")
    page = ProvidersPage(lambda: [], settings_store)

    page.tts_advanced_endpoint.setText("https://voice.example/tts")
    page.tts_voices_endpoint.setText("https://voice.example/voices")
    page._save_settings()

    saved = settings_store.load()
    assert saved.tts_advanced_endpoint == "https://voice.example/tts"
    assert saved.tts_voices_endpoint == "https://voice.example/voices"
