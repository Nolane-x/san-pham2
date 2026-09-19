from __future__ import annotations

import importlib.util
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.app import build_services
from nolane_studio.config import ProviderSettings, SettingsStore
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import ProvidersPage, StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Generated image project")
    scene_id = store.add_scene(
        "p1",
        "Explain why the moon appears to change shape.",
        image_prompt="A simple moon phase diagram with Earth and sunlight.",
    )
    return store, scene_id


def test_image_provider_is_configurable_and_registered_api_first():
    assert "image_base_url" in ProviderSettings.__dataclass_fields__
    assert "image_model" in ProviderSettings.__dataclass_fields__

    services = build_services(
        ProviderSettings(
            image_base_url="https://images.example/v1",
            image_model="image-model",
        )
    )

    descriptors = services.providers.find(image=True)
    assert [item.name for item in descriptors] == ["image-api"]
    assert descriptors[0].capabilities.image is True


def test_generated_image_service_persists_scene_asset_and_reuses_stable_slot(tmp_path):
    assert importlib.util.find_spec("nolane_studio.images") is not None

    from nolane_studio.images import GeneratedImageService

    class FakeImageProvider:
        def __init__(self):
            self.calls = []

        def generate(self, request):
            self.calls.append(request)
            return b"\x89PNG\r\n\x1a\nFAKE"

    store, scene_id = _store(tmp_path)
    fake = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register(
        "image-api",
        ProviderCapabilities(image=True),
        lambda: fake,
    )

    service = GeneratedImageService(store, registry, tmp_path / "workspace")
    artifact = service.generate_scene(
        "p1",
        scene_id,
        provider_name="image-api",
        style="whiteboard",
        size="1024x1024",
    )

    path = Path(artifact.path)
    assert path.exists()
    assert path.read_bytes().startswith(b"\x89PNG")
    assert artifact.media_id == f"image-{scene_id}"
    assert len(fake.calls) == 1
    assert "Pure white background." in fake.calls[0].prompt
    assert "Do not render long text" in fake.calls[0].prompt

    scene = store.list_scenes("p1")[0]
    assert scene["metadata"]["generated_image_media_id"] == artifact.media_id
    assert scene["metadata"]["generated_image_path"] == str(path)
    assert scene["metadata"]["generated_image_cache_key"]
    assert [item["id"] for item in store.list_media("p1") if item["kind"] == "image"] == [
        artifact.media_id
    ]

    again = service.generate_scene(
        "p1",
        scene_id,
        provider_name="image-api",
        style="whiteboard",
        size="1024x1024",
    )
    assert again.media_id == artifact.media_id
    assert len(fake.calls) == 1
    assert len([item for item in store.list_media("p1") if item["kind"] == "image"]) == 1

    store.update_scene(scene_id, image_prompt="A changed moon phase illustration.")
    service.generate_scene(
        "p1",
        scene_id,
        provider_name="image-api",
        style="whiteboard",
        size="1024x1024",
    )
    assert len(fake.calls) == 2


def test_studio_exposes_recovered_generate_image_actions(tmp_path):
    _app()
    store, _scene_id = _store(tmp_path)
    page = StudioPage(store)

    assert page.generate_image_button.text() == "Generate image"
    assert page.generate_all_images_button.text() == "Generate all images"


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
