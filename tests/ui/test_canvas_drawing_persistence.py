from __future__ import annotations

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _page(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Drawing demo")
    store.replace_scenes("p1", [Scene(0, "Opening scene")])
    page = StudioPage(store)
    page.load_project("p1", "Drawing demo", [])
    page.scenes.setCurrentRow(0)
    scene_id = store.list_scenes("p1")[0]["id"]
    return store, page, scene_id


def test_draw_mode_is_user_toggleable_and_routes_to_canvas(tmp_path):
    _store, page, _scene_id = _page(tmp_path)

    assert page.draw_button.isCheckable()
    assert not page.canvas.drawing_enabled

    page.draw_button.setChecked(True)
    assert page.canvas.drawing_enabled

    page.draw_button.setChecked(False)
    assert not page.canvas.drawing_enabled


def test_completed_freehand_stroke_is_persisted_as_scene_drawing_layer(tmp_path):
    store, page, scene_id = _page(tmp_path)
    page.draw_button.setChecked(True)

    page.canvas.drawing_completed.emit([(10.0, 20.0), (30.0, 40.0), (50.0, 70.0)])

    objects = store.list_visual_objects(scene_id)
    assert len(objects) == 1
    drawing = objects[0]
    assert drawing["kind"] == "drawing"
    assert drawing["x"] == 0.0
    assert drawing["y"] == 0.0
    assert drawing["width"] == 1280.0
    assert drawing["height"] == 720.0
    assert drawing["payload"]["points"] == [[10.0, 20.0], [30.0, 40.0], [50.0, 70.0]]
    assert drawing["payload"]["color"] == "#20232A"
    assert drawing["payload"]["stroke"] == 5.0
    assert page.canvas.object_count() == 1
    assert page.layers.currentItem().data(256) == drawing["id"]


def test_persisted_freehand_survives_scene_reload(tmp_path):
    store, page, scene_id = _page(tmp_path)
    page.draw_button.setChecked(True)
    page.canvas.drawing_completed.emit([(5.0, 6.0), (100.0, 120.0)])

    page._refresh_scenes(selected_id=scene_id)

    assert page.canvas.object_count() == 1
    objects = store.list_visual_objects(scene_id)
    assert objects[0]["payload"]["points"] == [[5.0, 6.0], [100.0, 120.0]]
