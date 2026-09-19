from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _page(tmp_path: Path, count: int = 3):
    _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Lifecycle")
    store.replace_scenes(
        "p1",
        [Scene(index, f"Scene {index + 1}") for index in range(count)],
    )
    page = StudioPage(store)
    page.load_project("p1", "Lifecycle", [])
    return store, page, store.list_scenes("p1")


def _base_state(scene_ids: list[str]) -> dict:
    return {
        "clips": {},
        "videoClips": [],
        "audioClips": [],
        "mediaOrder": list(scene_ids),
        "transitions": [],
        "sceneEdits": [],
    }


def test_duplicate_scene_keeps_timeline_exact_and_clones_scene_edit(tmp_path):
    store, page, scenes = _page(tmp_path, 2)
    first, second = scenes
    state = _base_state([first["id"], second["id"]])
    state["transitions"] = [
        {
            "from_id": first["id"],
            "to_id": second["id"],
            "effect": "fade",
            "duration": 0.4,
        }
    ]
    state["sceneEdits"] = [
        {
            "scene_id": first["id"],
            "trim_start": 0.2,
            "trim_end": 1.0,
            "speed": 1.5,
        }
    ]
    store.save_timeline("p1", state)

    page.scenes.setCurrentRow(0)
    page._duplicate_selected_scene()

    updated_scenes = store.list_scenes("p1")
    assert len(updated_scenes) == 3
    duplicate = updated_scenes[1]
    updated = store.load_timeline("p1")
    assert updated["mediaOrder"] == [
        first["id"],
        duplicate["id"],
        second["id"],
    ]
    assert updated.get("transitions", []) == []

    edits = {entry["scene_id"]: entry for entry in updated.get("sceneEdits", [])}
    assert set(edits) == {first["id"], duplicate["id"]}
    assert edits[first["id"]] == state["sceneEdits"][0]
    assert edits[duplicate["id"]] == {
        **state["sceneEdits"][0],
        "scene_id": duplicate["id"],
    }


def test_delete_scene_prunes_stale_transition_and_scene_edit(tmp_path):
    store, page, scenes = _page(tmp_path, 3)
    first, middle, last = scenes
    state = _base_state([scene["id"] for scene in scenes])
    state["transitions"] = [
        {
            "from_id": first["id"],
            "to_id": middle["id"],
            "effect": "fade",
            "duration": 0.3,
        },
        {
            "from_id": middle["id"],
            "to_id": last["id"],
            "effect": "wipeleft",
            "duration": 0.2,
        },
    ]
    state["sceneEdits"] = [
        {
            "scene_id": middle["id"],
            "trim_start": 0.1,
            "trim_end": 1.0,
            "speed": 1.0,
        },
        {
            "scene_id": last["id"],
            "trim_start": 0.0,
            "trim_end": 1.2,
            "speed": 1.0,
        },
    ]
    store.save_timeline("p1", state)

    page.scenes.setCurrentRow(1)
    page._delete_selected_scene()

    updated = store.load_timeline("p1")
    assert updated["mediaOrder"] == [first["id"], last["id"]]
    assert updated.get("transitions", []) == []
    assert updated.get("sceneEdits", []) == [state["sceneEdits"][1]]


def test_move_scene_rewrites_media_order_and_drops_nonadjacent_transitions(tmp_path):
    store, page, scenes = _page(tmp_path, 3)
    first, middle, last = scenes
    state = _base_state([scene["id"] for scene in scenes])
    state["transitions"] = [
        {
            "from_id": first["id"],
            "to_id": middle["id"],
            "effect": "fade",
            "duration": 0.3,
        },
        {
            "from_id": middle["id"],
            "to_id": last["id"],
            "effect": "fade",
            "duration": 0.3,
        },
    ]
    store.save_timeline("p1", state)

    page.scenes.setCurrentRow(2)
    page._move_selected_scene(-1)

    moved = store.list_scenes("p1")
    assert [scene["id"] for scene in moved] == [
        first["id"],
        last["id"],
        middle["id"],
    ]
    updated = store.load_timeline("p1")
    assert updated["mediaOrder"] == [
        first["id"],
        last["id"],
        middle["id"],
    ]
    assert updated.get("transitions", []) == []


def test_add_scene_extends_exact_media_order(tmp_path):
    store, page, scenes = _page(tmp_path, 2)
    store.save_timeline("p1", _base_state([scene["id"] for scene in scenes]))

    page._add_scene()

    updated_scenes = store.list_scenes("p1")
    updated = store.load_timeline("p1")
    assert updated["mediaOrder"] == [scene["id"] for scene in updated_scenes]


def test_delete_last_scene_rebuilds_single_blank_scene_order(tmp_path):
    store, page, scenes = _page(tmp_path, 1)
    original = scenes[0]
    state = _base_state([original["id"]])
    state["sceneEdits"] = [
        {
            "scene_id": original["id"],
            "trim_start": 0.0,
            "trim_end": 1.0,
            "speed": 1.0,
        }
    ]
    store.save_timeline("p1", state)

    page.scenes.setCurrentRow(0)
    page._delete_selected_scene()

    remaining = store.list_scenes("p1")
    assert len(remaining) == 1
    assert remaining[0]["id"] != original["id"]
    updated = store.load_timeline("p1")
    assert updated["mediaOrder"] == [remaining[0]["id"]]
    assert updated.get("sceneEdits", []) == []
    assert updated.get("transitions", []) == []


def test_scene_mutation_fails_closed_when_unrecovered_legacy_tracks_are_nonempty(tmp_path):
    store, page, scenes = _page(tmp_path, 2)
    state = _base_state([scene["id"] for scene in scenes])
    state["videoClips"] = [{"legacy": "opaque"}]
    store.save_timeline("p1", state)
    messages: list[str] = []
    page.status_message.connect(messages.append)

    page.scenes.setCurrentRow(0)
    page._duplicate_selected_scene()

    assert [scene["id"] for scene in store.list_scenes("p1")] == [
        scene["id"] for scene in scenes
    ]
    assert store.load_timeline("p1")["videoClips"] == [{"legacy": "opaque"}]
    assert messages
    assert "legacy" in messages[-1].lower()


def test_scene_mutation_fails_closed_on_nonadjacent_transition_before_graph_change(tmp_path):
    store, page, scenes = _page(tmp_path, 3)
    first, middle, last = scenes
    state = _base_state([scene["id"] for scene in scenes])
    state["transitions"] = [
        {
            "from_id": first["id"],
            "to_id": last["id"],
            "effect": "fade",
            "duration": 0.3,
        }
    ]
    store.save_timeline("p1", state)
    messages: list[str] = []
    page.status_message.connect(messages.append)

    page.scenes.setCurrentRow(1)
    page._delete_selected_scene()

    assert [scene["id"] for scene in store.list_scenes("p1")] == [
        first["id"],
        middle["id"],
        last["id"],
    ]
    assert messages
    assert "adjacent" in messages[-1].lower()
