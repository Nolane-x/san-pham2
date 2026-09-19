from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import VoiceRequest
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore
from nolane_studio.voice import VoiceFromContentService


class FakeAdvancedVoiceProvider:
    def __init__(self) -> None:
        self.requests: list[VoiceRequest] = []
        self.catalog_calls = 0

    def synthesize(self, request: VoiceRequest) -> bytes:
        self.requests.append(request)
        return f"AUDIO-{len(self.requests)}".encode("ascii")

    def list_voices(self) -> list[str]:
        self.catalog_calls += 1
        return ["narrator", "teacher"]


def _service(
    tmp_path: Path,
    *,
    capabilities: ProviderCapabilities,
) -> tuple[VoiceFromContentService, ProjectStore, str, FakeAdvancedVoiceProvider]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    scene_id = store.add_scene("p1", "Xin chào thế giới", voice_text="Xin chào thế giới")
    provider = FakeAdvancedVoiceProvider()
    registry = ProviderRegistry()
    registry.register("voice-test", capabilities, lambda: provider)
    service = VoiceFromContentService(store, registry, tmp_path / "generated")
    return service, store, scene_id, provider


def test_voice_service_routes_clone_and_design_inputs_and_hashes_reference_audio(tmp_path):
    service, store, scene_id, provider = _service(
        tmp_path,
        capabilities=ProviderCapabilities(tts=True, clone=True, design=True),
    )
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"VOICE-A")

    first = service.synthesize_scene(
        "p1",
        scene_id,
        provider_name="voice-test",
        reference_audio=reference,
        reference_text="Mẫu giọng tham chiếu",
        design_instructions="Warm Vietnamese teacher",
    )
    second = service.synthesize_scene(
        "p1",
        scene_id,
        provider_name="voice-test",
        reference_audio=reference,
        reference_text="Mẫu giọng tham chiếu",
        design_instructions="Warm Vietnamese teacher",
    )

    assert first == second
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.reference_audio == str(reference)
    assert request.reference_text == "Mẫu giọng tham chiếu"
    assert request.design_instructions == "Warm Vietnamese teacher"

    reference.write_bytes(b"VOICE-B")
    service.synthesize_scene(
        "p1",
        scene_id,
        provider_name="voice-test",
        reference_audio=reference,
        reference_text="Mẫu giọng tham chiếu",
        design_instructions="Warm Vietnamese teacher",
    )
    assert len(provider.requests) == 2

    metadata = store.list_scenes("p1")[0]["metadata"]
    assert metadata["voice_reference_audio"] == str(reference)
    assert metadata["voice_reference_hash"]
    assert metadata["voice_reference_text"] == "Mẫu giọng tham chiếu"
    assert metadata["voice_design_instructions"] == "Warm Vietnamese teacher"


def test_voice_service_rejects_clone_input_when_provider_does_not_advertise_clone(tmp_path):
    service, _store, scene_id, provider = _service(
        tmp_path,
        capabilities=ProviderCapabilities(tts=True),
    )
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"VOICE")

    with pytest.raises(RuntimeError, match="clone"):
        service.synthesize_scene(
            "p1",
            scene_id,
            provider_name="voice-test",
            reference_audio=reference,
        )

    assert provider.requests == []


def test_voice_service_rejects_design_input_when_provider_does_not_advertise_design(tmp_path):
    service, _store, scene_id, provider = _service(
        tmp_path,
        capabilities=ProviderCapabilities(tts=True),
    )

    with pytest.raises(RuntimeError, match="design"):
        service.synthesize_scene(
            "p1",
            scene_id,
            provider_name="voice-test",
            design_instructions="Deep documentary voice",
        )

    assert provider.requests == []


def test_voice_service_discovers_catalog_only_from_list_voices_capability(tmp_path):
    service, _store, _scene_id, provider = _service(
        tmp_path,
        capabilities=ProviderCapabilities(tts=True, list_voices=True),
    )

    assert service.list_voices("voice-test") == ["narrator", "teacher"]
    assert provider.catalog_calls == 1

    limited, _store2, _scene2, limited_provider = _service(
        tmp_path / "limited",
        capabilities=ProviderCapabilities(tts=True),
    )
    with pytest.raises(RuntimeError, match="list_voices"):
        limited.list_voices("voice-test")
    assert limited_provider.catalog_calls == 0
