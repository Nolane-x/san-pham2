from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def _qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening"), Scene(1, "Closing")])
    scenes = store.list_scenes("p1")
    return store, scenes


def _layer_ids(page):
    return [str(page.layers.item(row).data(0x0100)) for row in range(page.layers.count())]


def test_canvas_editor_renders_object_model_in_z_order():
    _qt_app()
    from nolane_studio.ui.widgets import CanvasEditor

    canvas = CanvasEditor()
    canvas.resize(900, 560)
    canvas.set_objects(
        [
            {
                "id": "shape-1",
                "kind": "shape",
                "name": "Background",
                "x": 20,
                "y": 30,
                "width": 400,
                "height": 220,
                "rotation": 0,
                "opacity": 1,
                "visible": True,
                "locked": False,
                "z_index": 0,
                "payload": {"shape": "rect", "fill": "#ffffff"},
            },
            {
                "id": "text-1",
                "kind": "text",
                "name": "Caption",
                "x": 80,
                "y": 260,
                "width": 500,
                "height": 90,
                "rotation": 5,
                "opacity": 0.7,
                "visible": True,
                "locked": False,
                "z_index": 1,
                "payload": {"text": "Recovered editor", "font_size": 36},
            },
        ]
    )

    assert canvas.object_ids() == ["shape-1", "text-1"]
    assert canvas.object_count() == 2
    assert canvas.object_geometry("text-1")[:4] == (80.0, 260.0, 500.0, 90.0)


def test_studio_loads_canvas_from_selected_scene_and_switches_scene(tmp_path):
    _qt_app()
    from nolane_studio.ui.pages import StudioPage

    store, scenes = _store(tmp_path)
    first = store.add_visual_object(scenes[0]["id"], "text", name="Opening title", payload={"text": "One"})
    second = store.add_visual_object(scenes[1]["id"], "shape", name="Closing shape")

    page = StudioPage(store)
    page.load_project("p1", "Demo", [])

    assert page.canvas.object_ids() == [first]
    assert page.layers.count() == 1
    assert page.layers.item(0).text() == "Opening title"

    page.scenes.setCurrentRow(1)

    assert page.canvas.object_ids() == [second]
    assert page.layers.count() == 1
    assert page.layers.item(0).text() == "Closing shape"


def test_layer_panel_lists_front_to_back_and_move_buttons_match_visual_depth(tmp_path):
    _qt_app()
    from nolane_studio.ui.pages import StudioPage

    store, scenes = _store(tmp_path)
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])

    page._add_text_object()
    page._add_shape_object()
    rows = store.list_visual_objects(scenes[0]["id"])
    back_id = rows[0]["id"]
    front_id = rows[1]["id"]

    # Storage/canvas remain back -> front (ascending z_index), while a layer
    # panel follows editor convention and presents the frontmost layer first.
    assert [row["kind"] for row in rows] == ["text", "shape"]
    assert page.canvas.object_ids() == [back_id, front_id]
    assert _layer_ids(page) == [front_id, back_id]

    # Up/"Move layer forward" moves the selected back layer toward the front.
    page.layers.setCurrentRow(1)
    selected = str(page.layers.currentItem().data(0x0100))
    assert selected == back_id
    page._move_selected_object(-1)

    assert [row["id"] for row in store.list_visual_objects(scenes[0]["id"])] == [front_id, back_id]
    assert page.canvas.object_ids() == [front_id, back_id]
    assert _layer_ids(page) == [back_id, front_id]
    assert str(page.layers.currentItem().data(0x0100)) == back_id

    # Down/"Move layer backward" is the exact inverse.
    page._move_selected_object(1)

    assert [row["id"] for row in store.list_visual_objects(scenes[0]["id"])] == [back_id, front_id]
    assert page.canvas.object_ids() == [back_id, front_id]
    assert _layer_ids(page) == [front_id, back_id]
    assert str(page.layers.currentItem().data(0x0100)) == back_id


def test_studio_object_transform_and_delete_remain_persisted_after_layer_refresh(tmp_path):
    _qt_app()
    from nolane_studio.ui.pages import StudioPage

    store, scenes = _store(tmp_path)
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])

    page._add_text_object()
    page._add_shape_object()
    rows = store.list_visual_objects(scenes[0]["id"])
    selected = rows[0]["id"]

    # The back object is the second row in the front-to-back panel.
    page.layers.setCurrentRow(1)
    assert str(page.layers.currentItem().data(0x0100)) == selected

    page._canvas_object_transform_changed(selected, 41.0, 52.0, 420.0, 240.0, 13.0)
    changed = next(row for row in store.list_visual_objects(scenes[0]["id"]) if row["id"] == selected)
    assert (changed["x"], changed["y"], changed["width"], changed["height"], changed["rotation"]) == (
        41.0,
        52.0,
        420.0,
        240.0,
        13.0,
    )

    page._delete_selected_object()
    assert len(store.list_visual_objects(scenes[0]["id"])) == 1

def _canvas_model(*, object_id="shape-1", z_index=0, payload=None):
    return {
        "id": object_id,
        "kind": "shape",
        "name": "Shape",
        "x": 20,
        "y": 30,
        "width": 400,
        "height": 220,
        "rotation": 0,
        "opacity": 1,
        "visible": True,
        "locked": False,
        "z_index": z_index,
        "payload": {"fill": "#ffffff"} if payload is None else payload,
    }


def test_canvas_editor_rejects_fractional_z_index_before_replacing_existing_state():
    _qt_app()
    from nolane_studio.ui.widgets import CanvasEditor

    canvas = CanvasEditor()
    canvas.set_objects([_canvas_model(object_id="stable")])

    with pytest.raises(
        ValueError,
        match=r"^visual object bad-z z_index must be a non-negative integer$",
    ):
        canvas.set_objects([_canvas_model(object_id="bad-z", z_index=0.5)])

    assert canvas.object_ids() == ["stable"]
    assert canvas.object_count() == 1


@pytest.mark.parametrize("payload", [[], [["fill", "#ffffff"]]])
def test_canvas_editor_rejects_non_mapping_payload_before_replacing_existing_state(payload):
    _qt_app()
    from nolane_studio.ui.widgets import CanvasEditor

    canvas = CanvasEditor()
    canvas.set_objects([_canvas_model(object_id="stable")])

    with pytest.raises(
        ValueError,
        match=r"^visual object bad-payload payload must be a mapping$",
    ):
        canvas.set_objects([_canvas_model(object_id="bad-payload", payload=payload)])

    assert canvas.object_ids() == ["stable"]
    assert canvas.object_count() == 1

