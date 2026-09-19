from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _page(tmp_path: Path, texts: tuple[str, ...] = ("First", "Second")):
    _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Split")
    store.replace_scenes(
        "p1",
        [Scene(index, text) for index, text in enumerate(texts)],
    )
    scenes = store.list_scenes("p1")
    for scene in scenes:
        store.update_scene_render_settings(
            scene["id"],
            reveal_duration=1.0,
            hold_duration=3.0,
            settings={"style": "whiteboard"},
        )
    page = StudioPage(store)
    page.load_project("p1", "Split", [])
    page.scenes.setCurrentRow(0)
    page._sync_scene_edit_editor()
    return store, page, scenes


def _base_state(scene_ids: list[str]) -> dict:
    return {
        "clips": {},
        "videoClips": [],
        "audioClips": [],
        "mediaOrder": list(scene_ids),
        "transitions": [],
        "sceneEdits": [],
    }


def test_split_controls_default_to_effective_midpoint(tmp_path):
    _store, page, _scenes = _page(tmp_path)

    assert page.scene_split_at_spin.isEnabled() is True
    assert page.scene_split_button.isEnabled() is True
    assert page.scene_split_at_spin.value() == pytest.approx(2.0, abs=0.001)


def test_split_scene_creates_contiguous_windows_and_preserves_outgoing_transition(tmp_path):
    store, page, scenes = _page(tmp_path)
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
    store.save_timeline("p1", state)

    page._sync_scene_edit_editor()
    page.scene_split_at_spin.setValue(1.5)
    page._split_selected_scene()

    after_scenes = store.list_scenes("p1")
    assert len(after_scenes) == 3
    left, right, following = after_scenes
    assert left["id"] == first["id"]
    assert following["id"] == second["id"]
    assert right["text"] == left["text"] == "First"

    timeline = store.load_timeline("p1")
    assert timeline["mediaOrder"] == [left["id"], right["id"], following["id"]]

    edits = {entry["scene_id"]: entry for entry in timeline["sceneEdits"]}
    assert edits[left["id"]] == {
        "scene_id": left["id"],
        "trim_start": 0.0,
        "trim_end": 1.5,
        "speed": 1.0,
    }
    assert edits[right["id"]] == {
        "scene_id": right["id"],
        "trim_start": 1.5,
        "trim_end": 4.0,
        "speed": 1.0,
    }
    assert timeline["transitions"] == [
        {
            "from_id": right["id"],
            "to_id": following["id"],
            "effect": "fade",
            "duration": 0.4,
        }
    ]
    assert page._selected_scene_id() == right["id"]


def test_split_scene_respects_existing_trim_window_and_speed(tmp_path):
    store, page, scenes = _page(tmp_path)
    first, second = scenes
    state = _base_state([first["id"], second["id"]])
    state["sceneEdits"] = [
        {
            "scene_id": first["id"],
            "trim_start": 0.5,
            "trim_end": 3.5,
            "speed": 2.0,
        }
    ]
    store.save_timeline("p1", state)

    page._sync_scene_edit_editor()
    assert page.scene_split_at_spin.value() == pytest.approx(0.75, abs=0.001)
    page.scene_split_at_spin.setValue(0.5)
    page._split_selected_scene()

    after_scenes = store.list_scenes("p1")
    left, right, _following = after_scenes
    edits = {
        entry["scene_id"]: entry
        for entry in store.load_timeline("p1")["sceneEdits"]
    }
    assert edits[left["id"]] == {
        "scene_id": left["id"],
        "trim_start": 0.5,
        "trim_end": 1.5,
        "speed": 2.0,
    }
    assert edits[right["id"]] == {
        "scene_id": right["id"],
        "trim_start": 1.5,
        "trim_end": 3.5,
        "speed": 2.0,
    }
    left_effective = (
        edits[left["id"]]["trim_end"] - edits[left["id"]]["trim_start"]
    ) / edits[left["id"]]["speed"]
    right_effective = (
        edits[right["id"]]["trim_end"] - edits[right["id"]]["trim_start"]
    ) / edits[right["id"]]["speed"]
    assert left_effective == pytest.approx(0.5)
    assert right_effective == pytest.approx(1.0)
    assert left_effective + right_effective == pytest.approx(1.5)


def test_split_scene_fails_closed_for_opaque_legacy_tracks(tmp_path):
    store, page, scenes = _page(tmp_path)
    state = _base_state([scene["id"] for scene in scenes])
    state["videoClips"] = [{"legacy": "opaque"}]
    store.save_timeline("p1", state)
    messages: list[str] = []
    page.status_message.connect(messages.append)

    page._sync_scene_edit_editor()
    page.scene_split_at_spin.setValue(1.0)
    page._split_selected_scene()

    assert [scene["id"] for scene in store.list_scenes("p1")] == [
        scene["id"] for scene in scenes
    ]
    assert messages
    assert "legacy" in messages[-1].lower()


def test_split_scene_rejects_boundary_without_mutating_project(tmp_path):
    store, page, scenes = _page(tmp_path)
    messages: list[str] = []
    page.status_message.connect(messages.append)

    # Bypass the widget minimum to exercise the method's own invariant.
    page.scene_split_at_spin.setMinimum(0.0)
    page.scene_split_at_spin.setValue(0.0)
    page._split_selected_scene()

    assert [scene["id"] for scene in store.list_scenes("p1")] == [
        scene["id"] for scene in scenes
    ]
    assert messages
    assert "inside" in messages[-1].lower() or "split" in messages[-1].lower()


def test_split_scene_keeps_incoming_transition_and_moves_outgoing_to_right_half(tmp_path):
    store, page, scenes = _page(tmp_path, ("Previous", "Source", "Next"))
    previous, source, following = scenes
    state = _base_state([scene["id"] for scene in scenes])
    state["transitions"] = [
        {
            "from_id": previous["id"],
            "to_id": source["id"],
            "effect": "wipeleft",
            "duration": 0.25,
        },
        {
            "from_id": source["id"],
            "to_id": following["id"],
            "effect": "fade",
            "duration": 0.4,
        },
    ]
    store.save_timeline("p1", state)

    page.scenes.setCurrentRow(1)
    page._sync_scene_edit_editor()
    page.scene_split_at_spin.setValue(1.0)
    page._split_selected_scene()

    after = store.list_scenes("p1")
    assert len(after) == 4
    prev_after, left, right, next_after = after
    assert prev_after["id"] == previous["id"]
    assert left["id"] == source["id"]
    assert next_after["id"] == following["id"]

    transitions = store.load_timeline("p1")["transitions"]
    assert transitions == [
        {
            "from_id": prev_after["id"],
            "to_id": left["id"],
            "effect": "wipeleft",
            "duration": 0.25,
        },
        {
            "from_id": right["id"],
            "to_id": next_after["id"],
            "effect": "fade",
            "duration": 0.4,
        },
    ]
    assert not any(
        item["from_id"] == left["id"] and item["to_id"] == right["id"]
        for item in transitions
    )
