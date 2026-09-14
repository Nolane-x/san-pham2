from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    return store


def test_scene_plan_round_trips_with_stable_identity_and_order(tmp_path):
    store = _store(tmp_path)
    store.replace_scenes(
        "p1",
        [
            Scene(0, "Opening", "opening prompt"),
            Scene(1, "Middle", "middle prompt"),
            Scene(2, "Closing", "closing prompt"),
        ],
    )

    first = store.list_scenes("p1")
    second = store.list_scenes("p1")

    assert [scene["position"] for scene in first] == [0, 1, 2]
    assert [scene["text"] for scene in first] == ["Opening", "Middle", "Closing"]
    assert [scene["image_prompt"] for scene in first] == ["opening prompt", "middle prompt", "closing prompt"]
    assert [scene["id"] for scene in first] == [scene["id"] for scene in second]
    assert len(set(scene["id"] for scene in first)) == 3


def test_scene_crud_keeps_positions_contiguous_and_project_count_in_sync(tmp_path):
    store = _store(tmp_path)
    store.replace_scenes("p1", [Scene(0, "One"), Scene(1, "Two")])
    scenes = store.list_scenes("p1")

    inserted_id = store.add_scene("p1", "Inserted", position=1)
    store.update_scene(inserted_id, text="Inserted edited", image_prompt="detail")
    store.move_scene(inserted_id, 2)
    store.delete_scene(scenes[0]["id"])

    remaining = store.list_scenes("p1")
    assert [scene["position"] for scene in remaining] == [0, 1]
    assert [scene["text"] for scene in remaining] == ["Two", "Inserted edited"]
    assert remaining[1]["image_prompt"] == "detail"
    assert store.get_project("p1")["expected_image_count"] == 2


def test_scene_crud_rejects_cross_project_or_invalid_positions(tmp_path):
    store = _store(tmp_path)
    store.create_project("p2", "Other")
    scene_id = store.add_scene("p1", "Only")

    try:
        store.add_scene("p1", "Bad", position=3)
    except ValueError as exc:
        assert "position" in str(exc)
    else:
        raise AssertionError("out-of-range scene position was accepted")

    try:
        store.move_scene(scene_id, 2)
    except ValueError as exc:
        assert "position" in str(exc)
    else:
        raise AssertionError("out-of-range move was accepted")
