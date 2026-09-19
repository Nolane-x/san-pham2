from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> ProjectStore:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Voice UX")
    store.add_scene("p1", "Xin chào", voice_text="Xin chào")
    return store


def test_studio_advanced_voice_controls_follow_advertised_capabilities_without_instantiating(tmp_path):
    _app()
    created = {"count": 0}

    class Provider:
        def synthesize(self, request):
            return b"AUDIO"

        def list_voices(self):
            return ["teacher"]

    def factory():
        created["count"] += 1
        return Provider()

    registry = ProviderRegistry()
    registry.register(
        "voice-advanced",
        ProviderCapabilities(tts=True, clone=True, design=True, list_voices=True),
        factory,
    )

    page = StudioPage(_store(tmp_path), providers=registry)

    assert created["count"] == 0
    assert page.voice_reference_audio_edit.isHidden() is False
    assert page.voice_reference_text_edit.isHidden() is False
    assert page.voice_design_edit.isHidden() is False
    assert page.load_voice_catalog_button.isHidden() is False
    assert created["count"] == 0


def test_studio_hides_unsupported_advanced_voice_controls(tmp_path):
    _app()
    registry = ProviderRegistry()
    registry.register(
        "tts-basic",
        ProviderCapabilities(tts=True),
        lambda: object(),
    )

    page = StudioPage(_store(tmp_path), providers=registry)

    assert page.voice_reference_audio_edit.isHidden() is True
    assert page.voice_reference_text_edit.isHidden() is True
    assert page.voice_design_edit.isHidden() is True
    assert page.load_voice_catalog_button.isHidden() is True


def test_studio_builds_voice_generation_options_from_explicit_controls(tmp_path):
    _app()
    registry = ProviderRegistry()
    registry.register(
        "voice-advanced",
        ProviderCapabilities(tts=True, clone=True, design=True, list_voices=True),
        lambda: object(),
    )
    page = StudioPage(_store(tmp_path), providers=registry)
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"VOICE")

    page.voice_language_edit.setText("vi-VN")
    page.voice_name_combo.setEditText("teacher")
    page.voice_speed_spin.setValue(1.15)
    page.voice_reference_audio_edit.setText(str(reference))
    page.voice_reference_text_edit.setText("Đây là giọng mẫu")
    page.voice_design_edit.setText("Warm educational narrator")

    assert page._voice_generation_options() == {
        "language": "vi-VN",
        "voice": "teacher",
        "speed": 1.15,
        "reference_audio": str(reference),
        "reference_text": "Đây là giọng mẫu",
        "design_instructions": "Warm educational narrator",
    }
