import importlib.util
from pathlib import Path

from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore


def test_voice_from_content_generates_scene_audio_and_reuses_stable_media_slot(tmp_path):
    assert importlib.util.find_spec("nolane_studio.voice") is not None

    from nolane_studio.voice import VoiceFromContentService

    class FakeTTS:
        def __init__(self):
            self.calls = []

        def synthesize(self, request):
            self.calls.append(request)
            return b"ID3-fake-voice"

    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Voice project")
    scene_id = store.add_scene("p1", "Xin chao the gioi", voice_text="Xin chao the gioi")

    fake = FakeTTS()
    registry = ProviderRegistry()
    registry.register("tts-api", ProviderCapabilities(tts=True), lambda: fake)

    service = VoiceFromContentService(store, registry, tmp_path / "workspace")
    artifact = service.synthesize_scene("p1", scene_id, provider_name="tts-api", language="vi-VN", voice="vi-demo")

    path = Path(artifact.path)
    assert path.exists()
    assert path.read_bytes() == b"ID3-fake-voice"
    assert artifact.media_id == f"voice-{scene_id}"

    scene = store.list_scenes("p1")[0]
    assert scene["metadata"]["voice_media_id"] == artifact.media_id
    assert scene["metadata"]["voice_path"] == str(path)
    assert scene["metadata"]["voice_cache_key"]
    assert [item["id"] for item in store.list_media("p1") if item["kind"] == "audio"] == [artifact.media_id]

    again = service.synthesize_scene(
        "p1", scene_id, provider_name="tts-api", language="vi-VN", voice="vi-demo"
    )
    assert again.media_id == artifact.media_id
    assert len([item for item in store.list_media("p1") if item["kind"] == "audio"]) == 1
    assert len(fake.calls) == 1

    store.update_scene(scene_id, voice_text="Noi dung moi")
    service.synthesize_scene(
        "p1", scene_id, provider_name="tts-api", language="vi-VN", voice="vi-demo"
    )
    assert len(fake.calls) == 2
