from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.config import SettingsStore
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import ProvidersPage, StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.add_scene("p1", "Opening scene", image_prompt="A simple opening diagram")
    return store


def test_studio_exposes_recovered_image_generation_actions(tmp_path):
    _app()
    page = StudioPage(_store(tmp_path))

    assert page.generate_image_button.text() == "Generate image"
    assert page.generate_all_images_button.text() == "Generate All Images"


def test_studio_resolves_live_image_provider_capability(tmp_path):
    _app()
    providers = ProviderRegistry()
    providers.register("image-test", ProviderCapabilities(image=True), lambda: object())

    page = StudioPage(_store(tmp_path), providers=providers)

    assert page._provider_name("image") == "image-test"


def test_provider_page_exposes_and_persists_image_settings(tmp_path):
    _app()
    settings_store = SettingsStore(tmp_path / "settings.json")
    page = ProvidersPage(lambda: [], settings_store)

    page.image_endpoint.setText("https://images.example/v1")
    page.image_model.setText("image-model")
    page._save_settings()

    saved = settings_store.load()
    assert saved.image_base_url == "https://images.example/v1"
    assert saved.image_model == "image-model"
