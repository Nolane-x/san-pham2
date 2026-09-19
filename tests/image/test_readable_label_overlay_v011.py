from __future__ import annotations

from pathlib import Path

import pytest

from nolane_studio.domain import ImageRequest
from nolane_studio.providers import ProviderCapabilities, ProviderRegistry
from nolane_studio.storage.store import ProjectStore


OWNER = "nolane-readable-label-overlay-v1"


def _analysis(*objects: dict) -> dict:
    return {
        "ai_analysis": {
            "scene_id": "scene",
            "transcript": "Revenue and costs",
            "words": [],
            "objects": list(objects),
            "content_hash": "analysis-v1",
        }
    }


def _object(label: str, box: list[float], *, phrase: str | None = None) -> dict:
    return {
        "label": label,
        "phrase": phrase or label,
        "box": box,
        "start": 0.0,
        "end": 1.0,
    }


def _store(tmp_path: Path, metadata: dict) -> tuple[ProjectStore, str, str]:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    scene_id = store.add_scene("p1", "Revenue and costs", metadata=metadata)
    manual_id = store.add_visual_object(
        scene_id,
        "text",
        name="Manual title",
        x=40,
        y=30,
        width=300,
        height=80,
        payload={"text": "Keep me", "font_size": 28},
    )
    return store, scene_id, manual_id


def _owned(rows: list[dict]) -> list[dict]:
    return [
        row
        for row in rows
        if row.get("payload", {}).get("nolane_owner") == OWNER
    ]


def test_grounded_readable_labels_create_editable_text_layers_and_are_idempotent(tmp_path):
    from nolane_studio.readable_labels import sync_readable_label_objects

    metadata = _analysis(
        _object("Revenue", [0.10, 0.20, 0.40, 0.35]),
        _object("Costs", [0.60, 0.50, 0.90, 0.70]),
    )
    store, scene_id, manual_id = _store(tmp_path, metadata)
    store.add_visual_object(
        scene_id,
        "image",
        name="Generated scene visual",
        source=str(tmp_path / "scene.png"),
        width=1280,
        height=720,
        payload={"generated": True},
    )

    first_ids = sync_readable_label_objects(store, scene_id, metadata)
    second_ids = sync_readable_label_objects(store, scene_id, metadata)

    assert second_ids == first_ids
    rows = store.list_visual_objects(scene_id)
    assert any(row["id"] == manual_id and row["payload"]["text"] == "Keep me" for row in rows)
    labels = _owned(rows)
    assert [row["id"] for row in labels] == list(first_ids)
    assert [row["payload"]["text"] for row in labels] == ["Revenue", "Costs"]
    assert [row["payload"]["analysis_index"] for row in labels] == [0, 1]
    assert labels[0]["x"] == pytest.approx(128.0)
    assert labels[0]["y"] == pytest.approx(144.0)
    assert labels[0]["width"] == pytest.approx(384.0)
    assert labels[0]["height"] == pytest.approx(108.0)
    assert labels[0]["kind"] == "text"


def test_grounded_readable_labels_update_owned_slots_remove_stale_and_preserve_manual_text(tmp_path):
    from nolane_studio.readable_labels import sync_readable_label_objects

    original = _analysis(
        _object("Revenue", [0.10, 0.20, 0.40, 0.35]),
        _object("Costs", [0.60, 0.50, 0.90, 0.70]),
    )
    store, scene_id, manual_id = _store(tmp_path, original)
    original_ids = sync_readable_label_objects(store, scene_id, original)

    changed = _analysis(_object("Profit", [0.20, 0.25, 0.55, 0.45]))
    changed["ai_analysis"]["content_hash"] = "analysis-v2"
    changed_ids = sync_readable_label_objects(store, scene_id, changed)

    assert changed_ids == (original_ids[0],)
    rows = store.list_visual_objects(scene_id)
    assert any(row["id"] == manual_id and row["payload"]["text"] == "Keep me" for row in rows)
    labels = _owned(rows)
    assert len(labels) == 1
    assert labels[0]["payload"]["text"] == "Profit"
    assert labels[0]["payload"]["analysis_content_hash"] == "analysis-v2"
    assert labels[0]["x"] == pytest.approx(256.0)
    assert labels[0]["width"] == pytest.approx(448.0)


def test_grounded_readable_labels_fail_closed_before_mutating_on_invalid_box(tmp_path):
    from nolane_studio.readable_labels import sync_readable_label_objects

    metadata = _analysis(_object("Revenue", [0.10, 0.20, 0.40, 0.35]))
    store, scene_id, _ = _store(tmp_path, metadata)
    sync_readable_label_objects(store, scene_id, metadata)
    before = store.list_visual_objects(scene_id)

    invalid = _analysis(
        _object("Broken", [0.80, 0.20, 0.30, 0.50]),
        _object("Would mutate", [0.10, 0.10, 0.20, 0.20]),
    )
    with pytest.raises(ValueError, match="label box"):
        sync_readable_label_objects(store, scene_id, invalid)

    assert store.list_visual_objects(scene_id) == before


def test_readable_label_validator_rejects_non_mapping_metadata():
    from nolane_studio.readable_labels import validate_readable_label_metadata

    with pytest.raises(ValueError, match="metadata must be a mapping"):
        validate_readable_label_metadata([])


class FakeImageProvider:
    def __init__(self) -> None:
        self.requests: list[ImageRequest] = []

    def generate(self, request: ImageRequest) -> bytes:
        self.requests.append(request)
        return b"PNG-DATA"


def test_image_generation_cache_hit_preserves_synced_analysis_labels(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService
    from nolane_studio.readable_labels import sync_readable_label_objects

    store, scene_id, manual_id = _store(tmp_path, {})
    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register(
        "image-test",
        ProviderCapabilities(image=True),
        lambda: provider,
    )
    service = ImageGenerationService(store, registry, tmp_path / "generated")

    service.generate_scene("p1", scene_id, provider_name="image-test")
    metadata = dict(store.list_scenes("p1")[0]["metadata"])
    metadata.update(_analysis(_object("Revenue", [0.10, 0.20, 0.40, 0.35])))
    store.update_scene(scene_id, metadata=metadata)
    first_ids = sync_readable_label_objects(store, scene_id, metadata)

    service.generate_scene("p1", scene_id, provider_name="image-test")
    second = _owned(store.list_visual_objects(scene_id))

    assert len(provider.requests) == 1
    assert [row["id"] for row in second] == list(first_ids)
    assert second[0]["payload"]["text"] == "Revenue"
    assert any(row["id"] == manual_id for row in store.list_visual_objects(scene_id))


def test_fresh_image_generation_invalidates_stale_analysis_and_owned_labels(tmp_path):
    from nolane_studio.image_generation import ImageGenerationService
    from nolane_studio.readable_labels import sync_readable_label_objects

    metadata = _analysis(_object("Old revenue", [0.10, 0.20, 0.40, 0.35]))
    store, scene_id, manual_id = _store(tmp_path, metadata)
    sync_readable_label_objects(store, scene_id, metadata)
    assert len(_owned(store.list_visual_objects(scene_id))) == 1

    provider = FakeImageProvider()
    registry = ProviderRegistry()
    registry.register(
        "image-test",
        ProviderCapabilities(image=True),
        lambda: provider,
    )
    ImageGenerationService(
        store,
        registry,
        tmp_path / "generated",
    ).generate_scene("p1", scene_id, provider_name="image-test")

    scene = store.list_scenes("p1")[0]
    assert "ai_analysis" not in scene["metadata"]
    assert _owned(store.list_visual_objects(scene_id)) == []
    assert any(row["id"] == manual_id for row in store.list_visual_objects(scene_id))
    assert len(provider.requests) == 1
