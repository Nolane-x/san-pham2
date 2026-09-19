from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _page(tmp_path, *, include_second_timing: bool = True):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening")])
    scene_id = store.list_scenes("p1")[0]["id"]

    first = store.add_visual_object(
        scene_id,
        "shape",
        name="Chart",
        x=30,
        y=40,
        width=320,
        height=180,
        payload={"fill": "#abcdef"},
    )
    second = store.add_visual_object(
        scene_id,
        "text",
        name="Caption",
        x=400,
        y=120,
        width=300,
        height=100,
        payload={"text": "Growth"},
    )

    timing = [
        {"object_id": first, "pause": 0.5, "draw": 1.25, "push": 0.25},
    ]
    if include_second_timing:
        timing.append(
            {"object_id": second, "pause": 0.1, "draw": 2.5, "push": 0.0}
        )

    store.update_scene_render_settings(
        scene_id,
        reveal_duration=6.0,
        hold_duration=1.0,
        settings={
            "style": "whiteboard",
            "object_timing_mode": "custom",
            "custom_object_timing_config": timing,
        },
    )

    page = StudioPage(store)
    page.load_project("p1", "Demo", [])
    page.scenes.setCurrentRow(0)
    return store, page, scene_id, first, second


def _select_layer(page: StudioPage, object_id: str) -> None:
    for row in range(page.layers.count()):
        item = page.layers.item(row)
        if str(item.data(Qt.ItemDataRole.UserRole) or "") == object_id:
            page.layers.setCurrentRow(row)
            return
    raise AssertionError(f"layer {object_id} not found")


def _timing_by_id(store: ProjectStore, scene_id: str) -> dict[str, dict]:
    settings = store.get_scene_render_settings(scene_id)
    return {
        str(entry["object_id"]): dict(entry)
        for entry in settings["custom_object_timing_config"]
    }


def test_object_timing_editor_tracks_selected_layer(tmp_path):
    _store, page, _scene_id, first, second = _page(tmp_path)

    _select_layer(page, first)
    assert "Chart" in page.object_timing_object_label.text()
    assert page.object_pause_spin.value() == pytest.approx(0.5)
    assert page.object_draw_spin.value() == pytest.approx(1.25)
    assert page.object_push_spin.value() == pytest.approx(0.25)

    _select_layer(page, second)
    assert "Caption" in page.object_timing_object_label.text()
    assert page.object_pause_spin.value() == pytest.approx(0.1)
    assert page.object_draw_spin.value() == pytest.approx(2.5)
    assert page.object_push_spin.value() == pytest.approx(0.0)


def test_object_timing_editor_uses_engine_fixed_share_for_missing_custom_entry(tmp_path):
    _store, page, _scene_id, _first, second = _page(
        tmp_path,
        include_second_timing=False,
    )

    _select_layer(page, second)

    # Engine authority: reveal 6s / 2 visible objects = 3s draw fallback.
    assert page.object_pause_spin.value() == pytest.approx(0.0)
    assert page.object_draw_spin.value() == pytest.approx(3.0)
    assert page.object_push_spin.value() == pytest.approx(0.0)


def test_saving_selected_object_timing_preserves_other_object_entries(tmp_path):
    store, page, scene_id, first, second = _page(tmp_path)

    _select_layer(page, second)
    page.object_pause_spin.setValue(0.75)
    page.object_draw_spin.setValue(1.5)
    page.object_push_spin.setValue(0.2)
    page._save_selected_object_timing()

    timing = _timing_by_id(store, scene_id)
    assert timing[first] == {
        "object_id": first,
        "pause": 0.5,
        "draw": 1.25,
        "push": 0.25,
    }
    assert timing[second] == {
        "object_id": second,
        "pause": 0.75,
        "draw": 1.5,
        "push": 0.2,
    }
    assert store.get_scene_render_settings(scene_id)["object_timing_mode"] == "custom"
