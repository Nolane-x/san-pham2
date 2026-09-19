from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.config import SettingsStore
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui import pages_base
from nolane_studio.ui.pages import ProvidersPage, StudioPage
from nolane_studio.ui.qt_window import MainWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.add_scene("p1", "Opening scene")
    return store


def test_studio_exposes_recovered_ai_analyze_and_voice_actions(tmp_path):
    _app()
    page = StudioPage(_store(tmp_path))

    assert page.ai_analyze_button.text() == "AI Analyze"
    assert page.analyze_all_button.text() == "Analyze All"
    assert page.generate_voice_button.text() == "Generate voice"
    assert page.voice_from_content_button.text() == "Voice From Content"
    assert page.attach_media_button.text() == "Attach"


def test_studio_accepts_live_provider_registry_for_capability_resolution(tmp_path):
    _app()
    providers = ProviderRegistry()
    providers.register(
        "tts-test",
        ProviderCapabilities(tts=True),
        lambda: object(),
    )

    page = StudioPage(_store(tmp_path), providers=providers)

    assert page.providers is providers
    assert page._provider_name("tts") == "tts-test"


def test_provider_page_exposes_and_persists_vision_and_stt_settings(tmp_path):
    _app()
    settings_store = SettingsStore(tmp_path / "settings.json")
    page = ProvidersPage(lambda: [], settings_store)

    page.vision_endpoint.setText("https://vision.example/v1")
    page.vision_model.setText("vision-model")
    page.stt_endpoint.setText("https://stt.example/v1")
    page.stt_model.setText("stt-model")
    page._save_settings()

    saved = settings_store.load()
    assert saved.vision_base_url == "https://vision.example/v1"
    assert saved.vision_model == "vision-model"
    assert saved.stt_base_url == "https://stt.example/v1"
    assert saved.stt_model == "stt-model"


def test_studio_import_media_accepts_audio_for_analysis_and_voice(tmp_path, monkeypatch):
    _app()
    store = _store(tmp_path)
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])

    source = tmp_path / "narration.mp3"
    source.write_bytes(b"ID3-audio")
    monkeypatch.setattr(
        pages_base.QFileDialog,
        "getOpenFileNames",
        lambda *args, **kwargs: ([str(source)], ""),
    )

    page._import_media()

    media = store.list_media("p1")
    assert len(media) == 1
    assert media[0]["kind"] == "audio"
    assert Path(media[0]["file_path"]).read_bytes() == b"ID3-audio"


def test_studio_attach_audio_updates_selected_scene_metadata(tmp_path):
    _app()
    store = _store(tmp_path)
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"ID3-voice")
    media_id = store.add_media(
        "p1",
        "audio",
        "voice.mp3",
        str(audio),
        media_id="audio-1",
    )
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])
    page.media_list.setCurrentRow(0)

    page._attach_selected_media()

    scene = store.list_scenes("p1")[0]
    assert scene["metadata"]["voice_media_id"] == media_id
    assert scene["metadata"]["voice_path"] == str(audio)


def test_main_window_passes_registry_to_studio_and_descriptors_to_provider_page(tmp_path):
    _app()
    store = _store(tmp_path)
    providers = ProviderRegistry()
    providers.register(
        "vision-test",
        ProviderCapabilities(vision=True),
        lambda: object(),
    )
    settings_store = SettingsStore(tmp_path / "settings.json")

    window = MainWindow(store, providers, settings_store)

    assert window.studio_page.providers is providers
    assert [item.name for item in window.providers_page.provider_descriptors()] == ["vision-test"]
