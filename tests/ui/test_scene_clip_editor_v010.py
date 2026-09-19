from __future__ import annotations

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _page(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Scene clip edits")
    store.replace_scenes(
        "p1",
        [Scene(0, "First"), Scene(1, "Second")],
    )
    scenes = store.list_scenes("p1")
    page = StudioPage(store)
    page.load_project("p1", "Scene clip edits", [])
    page.scenes.setCurrentRow(0)
    return store, page, scenes


def test_scene_clip_editor_tracks_selected_scene_and_full_duration_default(tmp_path):
    _store, page, _scenes = _page(tmp_path)

    assert page.scene_edit_label.text().startswith("Clip edit · Scene 1")
    assert page.scene_trim_start_spin.isEnabled() is True
    assert page.scene_trim_end_spin.isEnabled() is True
    assert page.scene_speed_spin.isEnabled() is True
    assert page.scene_edit_save_button.isEnabled() is True
    assert page.scene_edit_reset_button.isEnabled() is True
    assert page.scene_trim_start_spin.value() == 0.0
    assert page.scene_trim_end_spin.value() > 0.0
    assert page.scene_speed_spin.value() == 1.0


def test_scene_clip_editor_save_preserves_other_edits_and_transition_state(tmp_path):
    store, page, scenes = _page(tmp_path)
    first, second = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"], second["id"]],
            "transitions": [
                {
                    "from_id": first["id"],
                    "to_id": second["id"],
                    "effect": "fade",
                    "duration": 0.5,
                }
            ],
            "sceneEdits": [
                {
                    "scene_id": second["id"],
                    "trim_start": 0.25,
                    "trim_end": 1.25,
                    "speed": 1.25,
                }
            ],
        },
    )

    page.scenes.setCurrentRow(1)
    page.scenes.setCurrentRow(0)
    page._sync_scene_edit_editor()
    page.scene_trim_start_spin.setValue(0.5)
    page.scene_trim_end_spin.setValue(1.5)
    page.scene_speed_spin.setValue(2.0)
    page._save_selected_scene_edit()

    state = store.load_timeline("p1")
    by_scene = {entry["scene_id"]: entry for entry in state["sceneEdits"]}
    assert by_scene[first["id"]] == {
        "scene_id": first["id"],
        "trim_start": 0.5,
        "trim_end": 1.5,
        "speed": 2.0,
    }
    assert by_scene[second["id"]] == {
        "scene_id": second["id"],
        "trim_start": 0.25,
        "trim_end": 1.25,
        "speed": 1.25,
    }
    assert state["transitions"] == [
        {
            "from_id": first["id"],
            "to_id": second["id"],
            "effect": "fade",
            "duration": 0.5,
        }
    ]
    assert state["clips"] == {}
    assert state["videoClips"] == []
    assert state["audioClips"] == []


def test_scene_clip_editor_loads_and_resets_only_selected_scene_edit(tmp_path):
    store, page, scenes = _page(tmp_path)
    first, second = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"], second["id"]],
            "sceneEdits": [
                {
                    "scene_id": first["id"],
                    "trim_start": 0.5,
                    "trim_end": 1.5,
                    "speed": 1.5,
                },
                {
                    "scene_id": second["id"],
                    "trim_start": 0.25,
                    "trim_end": 1.25,
                    "speed": 1.25,
                },
            ],
        },
    )

    page._sync_scene_edit_editor()
    assert page.scene_trim_start_spin.value() == 0.5
    assert page.scene_trim_end_spin.value() == 1.5
    assert page.scene_speed_spin.value() == 1.5

    page._reset_selected_scene_edit()

    state = store.load_timeline("p1")
    assert state["sceneEdits"] == [
        {
            "scene_id": second["id"],
            "trim_start": 0.25,
            "trim_end": 1.25,
            "speed": 1.25,
        }
    ]
    assert page.scene_trim_start_spin.value() == 0.0
    assert page.scene_trim_end_spin.value() > 0.0
    assert page.scene_speed_spin.value() == 1.0


def test_scene_clip_editor_fails_closed_on_invalid_persisted_entry(tmp_path):
    store, page, _scenes = _page(tmp_path)
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [],
            "sceneEdits": ["not-a-mapping"],
        },
    )

    page._sync_scene_edit_editor()

    assert page.scene_edit_save_button.isEnabled() is False
    assert page.scene_edit_reset_button.isEnabled() is False
    assert "invalid" in page.scene_edit_label.text().lower()
