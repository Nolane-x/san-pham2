from __future__ import annotations

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _page(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Transitions")
    store.replace_scenes(
        "p1",
        [Scene(0, "First"), Scene(1, "Second"), Scene(2, "Third")],
    )
    scenes = store.list_scenes("p1")
    page = StudioPage(store)
    page.load_project("p1", "Transitions", [])
    page.scenes.setCurrentRow(0)
    return store, page, scenes


def test_transition_editor_persists_selected_scene_to_next_scene(tmp_path):
    store, page, scenes = _page(tmp_path)
    first, second, _third = scenes

    assert page.transition_effect_combo.isEnabled() is True
    assert page.transition_pair_label.text()
    page.transition_effect_combo.setCurrentIndex(
        page.transition_effect_combo.findData("fade")
    )
    page.transition_duration_spin.setValue(0.75)
    page._save_selected_transition()

    state = store.load_timeline("p1")
    assert state["transitions"] == [
        {
            "from_id": first["id"],
            "to_id": second["id"],
            "effect": "fade",
            "duration": 0.75,
        }
    ]
    assert state["clips"] == {}
    assert state["videoClips"] == []
    assert state["audioClips"] == []


def test_transition_editor_loads_existing_pair_without_instantiating_new_timeline_schema(tmp_path):
    store, page, scenes = _page(tmp_path)
    first, second, third = scenes
    store.save_timeline(
        "p1",
        {
            "clips": {},
            "videoClips": [],
            "audioClips": [],
            "mediaOrder": [first["id"], second["id"], third["id"]],
            "transitions": [
                {
                    "from_id": first["id"],
                    "to_id": second["id"],
                    "effect": "wipeleft",
                    "duration": 1.25,
                }
            ],
        },
    )

    page.scenes.setCurrentRow(1)
    page.scenes.setCurrentRow(0)
    page._sync_transition_editor()

    assert page.transition_effect_combo.currentData() == "wipeleft"
    assert page.transition_duration_spin.value() == 1.25
    assert page.transition_save_button.isEnabled() is True


def test_transition_editor_disables_pair_controls_for_last_scene(tmp_path):
    _store, page, scenes = _page(tmp_path)

    page.scenes.setCurrentRow(len(scenes) - 1)
    page._sync_transition_editor()

    assert page.transition_effect_combo.isEnabled() is False
    assert page.transition_duration_spin.isEnabled() is False
    assert page.transition_save_button.isEnabled() is False
    assert page.transition_clear_button.isEnabled() is False
