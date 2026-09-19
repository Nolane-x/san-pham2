from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.ai.object_voice import GroundedObject, TranscriptWord
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.readable_labels import READABLE_LABEL_OWNER
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


class FakeStt:
    def transcribe_with_timestamps(self, audio_bytes: bytes, *, language=None):
        assert audio_bytes
        return [TranscriptWord("Revenue", 0.0, 1.0)]


class FakeVision:
    def ground_objects(self, image_bytes: bytes, *, transcript: str, target_phrases=None):
        assert image_bytes
        assert transcript == "Revenue"
        return [GroundedObject("Revenue", "Revenue", (0.1, 0.2, 0.4, 0.35))]


def test_ai_analyze_materializes_grounded_readable_label_without_regenerating_image(tmp_path: Path):
    _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")

    image = tmp_path / "scene.png"
    voice = tmp_path / "scene.wav"
    image.write_bytes(b"fake-image")
    voice.write_bytes(b"fake-audio")
    scene_id = store.add_scene(
        "p1",
        "Revenue",
        metadata={
            "visual_path": str(image),
            "image_path": str(image),
            "voice_path": str(voice),
        },
    )
    image_object_id = store.add_visual_object(
        scene_id,
        "image",
        name="Generated scene visual",
        source=str(image),
        width=1280,
        height=720,
        payload={"generated": True, "media_id": f"image-{scene_id}"},
        z_index=0,
    )

    providers = ProviderRegistry()
    providers.register("stt-test", ProviderCapabilities(stt=True), FakeStt)
    providers.register("vision-test", ProviderCapabilities(vision=True), FakeVision)

    page = StudioPage(store, providers=providers)
    page.load_project("p1", "Demo", [])
    result = page._analyze_scene_sync(scene_id)

    assert [item.label for item in result.objects] == ["Revenue"]
    rows = store.list_visual_objects(scene_id)
    assert any(row["id"] == image_object_id for row in rows)
    labels = [
        row
        for row in rows
        if row["payload"].get("nolane_owner") == READABLE_LABEL_OWNER
    ]
    assert len(labels) == 1
    assert labels[0]["kind"] == "text"
    assert labels[0]["payload"]["text"] == "Revenue"
    assert labels[0]["x"] == 128.0
    assert labels[0]["y"] == 144.0

    metadata = store.list_scenes("p1")[0]["metadata"]
    assert metadata["ai_analysis"]["objects"][0]["label"] == "Revenue"
