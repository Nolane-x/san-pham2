from __future__ import annotations

import pytest

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore


def _store(tmp_path):
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening")])
    return store, store.list_scenes("p1")[0]["id"]


def test_visual_objects_round_trip_with_stable_ids_transform_and_z_order(tmp_path):
    store, scene_id = _store(tmp_path)

    first_id = store.add_visual_object(
        scene_id,
        "image",
        name="Hero",
        source="media-1",
        x=120,
        y=90,
        width=640,
        height=360,
        rotation=12.5,
        opacity=0.8,
        payload={"fit": "contain", "reveal": "draw"},
    )
    second_id = store.add_visual_object(
        scene_id,
        "text",
        name="Caption",
        x=80,
        y=560,
        width=900,
        height=90,
        payload={"text": "Hello", "font_size": 42},
    )

    rows = store.list_visual_objects(scene_id)

    assert [row["id"] for row in rows] == [first_id, second_id]
    assert [row["z_index"] for row in rows] == [0, 1]
    assert rows[0]["kind"] == "image"
    assert rows[0]["source"] == "media-1"
    assert rows[0]["x"] == 120
    assert rows[0]["y"] == 90
    assert rows[0]["width"] == 640
    assert rows[0]["height"] == 360
    assert rows[0]["rotation"] == 12.5
    assert rows[0]["opacity"] == 0.8
    assert rows[0]["payload"] == {"fit": "contain", "reveal": "draw"}
    assert rows[1]["payload"]["text"] == "Hello"


def test_visual_object_crud_keeps_z_order_contiguous_and_persists_transform(tmp_path):
    store, scene_id = _store(tmp_path)
    a = store.add_visual_object(scene_id, "shape", name="A")
    b = store.add_visual_object(scene_id, "shape", name="B")
    c = store.add_visual_object(scene_id, "shape", name="C")

    store.update_visual_object(
        b,
        x=24.5,
        y=18.0,
        width=320,
        height=180,
        rotation=-15,
        opacity=0.55,
        visible=False,
        locked=True,
        payload={"shape": "rect", "fill": "#ffffff"},
    )
    store.move_visual_object(c, 0)
    store.delete_visual_object(a)

    rows = store.list_visual_objects(scene_id)
    assert [row["id"] for row in rows] == [c, b]
    assert [row["z_index"] for row in rows] == [0, 1]
    edited = rows[1]
    assert edited["x"] == 24.5
    assert edited["y"] == 18.0
    assert edited["width"] == 320
    assert edited["height"] == 180
    assert edited["rotation"] == -15
    assert edited["opacity"] == 0.55
    assert edited["visible"] is False
    assert edited["locked"] is True
    assert edited["payload"]["shape"] == "rect"


def test_visual_objects_are_scene_scoped_and_scene_delete_cascades(tmp_path):
    store, scene_id = _store(tmp_path)
    other_scene = store.add_scene("p1", "Second")
    store.add_visual_object(scene_id, "text", payload={"text": "first"})
    store.add_visual_object(other_scene, "text", payload={"text": "second"})

    assert len(store.list_visual_objects(scene_id)) == 1
    assert len(store.list_visual_objects(other_scene)) == 1

    store.delete_scene(scene_id)

    assert store.list_visual_objects(scene_id) == []
    assert len(store.list_visual_objects(other_scene)) == 1


def test_visual_object_validation_rejects_invalid_geometry_and_kind(tmp_path):
    store, scene_id = _store(tmp_path)

    with pytest.raises(ValueError):
        store.add_visual_object(scene_id, "unknown")
    with pytest.raises(ValueError):
        store.add_visual_object(scene_id, "image", width=0)
    with pytest.raises(ValueError):
        store.add_visual_object(scene_id, "image", height=-1)
    with pytest.raises(ValueError):
        store.add_visual_object(scene_id, "image", opacity=1.2)



@pytest.mark.parametrize("field", ["visible", "locked"])
@pytest.mark.parametrize("value", ["false", 2])
def test_visual_object_read_rejects_non_boolean_persisted_flags(tmp_path, field, value):
    store, scene_id = _store(tmp_path)
    object_id = store.add_visual_object(scene_id, "shape", name="Flag integrity")

    with store._connect() as conn:
        conn.execute(
            f"UPDATE visual_editor_objects SET {field}=? WHERE id=?",
            (value, object_id),
        )

    with pytest.raises(
        ValueError,
        match=rf"^visual object {object_id} {field} must be stored as 0 or 1$",
    ):
        store.list_visual_objects(scene_id)



def test_visual_object_read_rejects_duplicate_persisted_z_index_even_when_hidden(tmp_path):
    store, scene_id = _store(tmp_path)
    first = store.add_visual_object(scene_id, "shape", name="Back")
    second = store.add_visual_object(
        scene_id,
        "text",
        name="Hidden front",
        visible=False,
        payload={"text": "hidden"},
    )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET z_index=0 WHERE id=?",
            (second,),
        )

    with pytest.raises(
        ValueError,
        match=rf"^scene {scene_id} visual object z_index 0 must be unique$",
    ):
        store.list_visual_objects(scene_id)

    assert first != second



@pytest.mark.parametrize(
    ("corrupt_id", "message"),
    [
        ("", "contains hidden visual object with blank id"),
        ("  hidden-object  ", "contains hidden visual object with noncanonical id '  hidden-object  '"),
    ],
)
def test_visual_object_read_rejects_hidden_noncanonical_identity(tmp_path, corrupt_id, message):
    store, scene_id = _store(tmp_path)
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Hidden identity integrity",
        visible=False,
    )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET id=? WHERE id=?",
            (corrupt_id, object_id),
        )

    with pytest.raises(
        ValueError,
        match=rf"^scene {scene_id} {message}$",
    ):
        store.list_visual_objects(scene_id)



def test_visual_object_read_rejects_hidden_non_mapping_payload(tmp_path):
    store, scene_id = _store(tmp_path)
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Hidden payload integrity",
        visible=False,
        payload={"fill": "#ffffff"},
    )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET payload_json=? WHERE id=?",
            ("[]", object_id),
        )

    with pytest.raises(
        ValueError,
        match=rf"^scene {scene_id} hidden visual object {object_id} payload must be a mapping$",
    ):
        store.list_visual_objects(scene_id)



def test_visual_object_read_rejects_hidden_unknown_kind(tmp_path):
    store, scene_id = _store(tmp_path)
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Hidden kind integrity",
        visible=False,
    )

    with store._connect() as conn:
        conn.execute(
            "UPDATE visual_editor_objects SET kind=? WHERE id=?",
            ("widget", object_id),
        )

    with pytest.raises(
        ValueError,
        match=(
            rf"^scene {scene_id} hidden visual object {object_id} kind must be one of: "
            r"drawing, image, shape, text, video$"
        ),
    ):
        store.list_visual_objects(scene_id)



@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("width", 0, "width must be > 0"),
        ("height", -1, "height must be > 0"),
        ("opacity", 1.2, "opacity must be within 0..1"),
    ],
)
def test_visual_object_read_rejects_hidden_writer_impossible_geometry(
    tmp_path,
    field,
    value,
    message,
):
    store, scene_id = _store(tmp_path)
    object_id = store.add_visual_object(
        scene_id,
        "shape",
        name="Hidden geometry integrity",
        visible=False,
    )

    with store._connect() as conn:
        conn.execute(
            f"UPDATE visual_editor_objects SET {field}=? WHERE id=?",
            (value, object_id),
        )

    with pytest.raises(
        ValueError,
        match=rf"^scene {scene_id} hidden visual object {object_id} {message}$",
    ):
        store.list_visual_objects(scene_id)
