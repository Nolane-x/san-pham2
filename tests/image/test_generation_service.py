from __future__ import annotations

from pathlib import Path

from nolane_studio.domain import ImageRequest
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore


class FakeImageProvider:
    def __init__(self) -> None:
        self.requests: list[ImageRequest] = []

    def generate(self, request: ImageRequest) -> bytes:
        self.requests.append(request)
        return b"PNG-DATA-" + str(len(self.requests)).encode("ascii")


def _store(tmp_path: Path) -> tuple[ProjectStore, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    scene_id = store.add_scene(
        "p1",
        "Revenue increased by twenty five percent.",
        image_prompt="A rising chart beside a small shop owner",
    )
    return store, scene_id


def test_generated_image_service_persists_stable_scene_media_and_reuses_cache(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService

    store, scene_id = _store(tmp_path)
    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register(
        "image-test",
        ProviderCapabilities(image=True),
        lambda: provider,
    )
    service = ImageGenerationService(store, registry, tmp_path / "generated")

    first = service.generate_scene("p1", scene_id, provider_name="image-test")
    second = service.generate_scene("p1", scene_id, provider_name="image-test")

    assert first == second
    assert first.media_id == f"image-{scene_id}"
    assert Path(first.path).read_bytes() == b"PNG-DATA-1"
    assert len(provider.requests) == 1
    assert provider.requests[0].size == "1024x1024"
    assert "pure white background" in provider.requests[0].prompt.lower()
    assert "do not render long text" in provider.requests[0].prompt.lower()

    media = store.list_media("p1")
    assert [item["id"] for item in media] == [f"image-{scene_id}"]
    scene = store.list_scenes("p1")[0]
    metadata = scene["metadata"]
    assert metadata["visual_media_id"] == f"image-{scene_id}"
    assert metadata["visual_path"] == first.path
    assert metadata["image_provider"] == "image-test"
    assert metadata["image_size"] == "1024x1024"
    assert metadata["image_cache_key"]
    assert metadata["image_object_id"]

    objects = store.list_visual_objects(scene_id)
    assert len(objects) == 1
    assert objects[0]["id"] == metadata["image_object_id"]
    assert objects[0]["kind"] == "image"
    assert objects[0]["source"] == first.path
    assert objects[0]["payload"] == {
        "media_id": f"image-{scene_id}",
        "fit": "contain",
        "generated": True,
    }

    service.generate_scene("p1", scene_id, provider_name="image-test")
    objects_after_cache_hit = store.list_visual_objects(scene_id)
    assert [item["id"] for item in objects_after_cache_hit] == [metadata["image_object_id"]]


def test_generated_image_cache_invalidates_when_scene_prompt_changes(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService

    store, scene_id = _store(tmp_path)
    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register(
        "image-test",
        ProviderCapabilities(image=True),
        lambda: provider,
    )
    service = ImageGenerationService(store, registry, tmp_path / "generated")

    first = service.generate_scene("p1", scene_id, provider_name="image-test")
    store.update_scene(scene_id, image_prompt="A completely different visual composition")
    second = service.generate_scene("p1", scene_id, provider_name="image-test")

    assert first.path == second.path
    assert len(provider.requests) == 2
    assert Path(second.path).read_bytes() == b"PNG-DATA-2"


def test_generate_project_creates_one_stable_image_slot_per_scene(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService

    store, first_id = _store(tmp_path)
    second_id = store.add_scene("p1", "Closing scene", image_prompt="A simple closing icon")
    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register("image-test", ProviderCapabilities(image=True), lambda: provider)

    artifacts = ImageGenerationService(
        store,
        registry,
        tmp_path / "generated",
    ).generate_project("p1", provider_name="image-test")

    assert [item.scene_id for item in artifacts] == [first_id, second_id]
    assert [item.media_id for item in artifacts] == [
        f"image-{first_id}",
        f"image-{second_id}",
    ]
    assert len(provider.requests) == 2


def test_generated_image_does_not_hijack_manual_image_object_from_stale_metadata(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService

    store, scene_id = _store(tmp_path)
    manual = tmp_path / "manual.png"
    manual.write_bytes(b"MANUAL")
    manual_id = store.add_visual_object(
        scene_id,
        "image",
        name="Manual image",
        source=str(manual),
        payload={"media_id": "manual-media", "fit": "contain"},
    )
    scene = store.list_scenes("p1")[0]
    metadata = dict(scene["metadata"])
    metadata["image_object_id"] = manual_id
    store.update_scene(scene_id, metadata=metadata)

    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register("image-test", ProviderCapabilities(image=True), lambda: provider)

    artifact = ImageGenerationService(
        store,
        registry,
        tmp_path / "generated",
    ).generate_scene("p1", scene_id, provider_name="image-test")

    objects = store.list_visual_objects(scene_id)
    manual_after = next(item for item in objects if item["id"] == manual_id)
    assert manual_after["name"] == "Manual image"
    assert manual_after["source"] == str(manual)
    assert manual_after["payload"] == {"media_id": "manual-media", "fit": "contain"}

    generated = [
        item
        for item in objects
        if item["payload"].get("generated") is True
    ]
    assert len(generated) == 1
    assert generated[0]["source"] == artifact.path
    assert generated[0]["id"] != manual_id
    assert store.list_scenes("p1")[0]["metadata"]["image_object_id"] == generated[0]["id"]
