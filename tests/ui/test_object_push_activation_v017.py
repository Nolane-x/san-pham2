from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


class FakeMediaExporter:
    def __init__(self) -> None:
        self.calls = []

    def export(self, clips, output, **kwargs):
        clips = list(clips)
        self.calls.append((clips, Path(output), kwargs))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _select_layer(page: StudioPage, object_id: str) -> None:
    for row in range(page.layers.count()):
        item = page.layers.item(row)
        if str(item.data(Qt.ItemDataRole.UserRole) or "") == object_id:
            page.layers.setCurrentRow(row)
            return
    raise AssertionError(f"layer {object_id} not found")


def _page(tmp_path: Path):
    app = _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Push activation")
    store.replace_scenes("p1", [Scene(0, "Push")])
    scene = store.list_scenes("p1")[0]
    first = store.add_visual_object(
        scene["id"],
        "shape",
        name="First",
        payload={"fill": "#FF0000"},
    )
    second = store.add_visual_object(
        scene["id"],
        "shape",
        name="Second",
        payload={"fill": "#00FF00"},
    )
    store.update_scene_render_settings(
        scene["id"],
        reveal_duration=1.0,
        hold_duration=0.5,
        settings={
            "style": "whiteboard",
            "large_object_push_enabled": False,
            "large_object_push_mode": "automatic",
            "large_object_push_direction": "from_left",
            "object_timing_mode": "custom",
            "custom_object_timing_config": [
                {"object_id": first, "draw": 0.5, "push": 0.0},
                {"object_id": second, "draw": 0.5, "push": 0.0},
            ],
        },
    )
    page = StudioPage(store)
    page.load_project("p1", "Push activation", [])
    app.processEvents()
    return app, store, page, scene, first, second


def test_saving_positive_visible_push_enables_recovered_push_contract(tmp_path):
    _app_obj, store, page, scene, _first, second = _page(tmp_path)
    _select_layer(page, second)
    page.object_push_spin.setValue(0.25)
    page._save_selected_object_timing()

    settings = store.get_scene_render_settings(scene["id"])
    assert settings["large_object_push_enabled"] is True
    assert settings["large_object_push_mode"] == "automatic"
    assert settings["large_object_push_direction"] == "from_left"


def test_resetting_last_positive_visible_push_disables_recovered_push_contract(tmp_path):
    _app_obj, store, page, scene, _first, second = _page(tmp_path)
    _select_layer(page, second)
    page.object_push_spin.setValue(0.25)
    page._save_selected_object_timing()
    assert store.get_scene_render_settings(scene["id"])["large_object_push_enabled"] is True

    page._reset_selected_object_timing()
    settings = store.get_scene_render_settings(scene["id"])
    assert settings["large_object_push_enabled"] is False


def test_hidden_stale_positive_timing_does_not_keep_scene_push_enabled(tmp_path):
    _app_obj, store, page, scene, first, _second = _page(tmp_path)
    hidden = store.add_visual_object(
        scene["id"],
        "shape",
        name="Hidden",
        visible=False,
        payload={"fill": "#0000FF"},
    )
    settings = store.get_scene_render_settings(scene["id"])
    timing = list(settings["custom_object_timing_config"])
    timing.append({"object_id": hidden, "draw": 0.2, "push": 0.8})
    store.update_scene_render_settings(
        scene["id"],
        settings={
            "large_object_push_enabled": True,
            "custom_object_timing_config": timing,
        },
    )
    page._load_render_controls(scene["id"])
    page._refresh_canvas_objects()
    _select_layer(page, first)
    page.object_push_spin.setValue(0.0)
    page._save_selected_object_timing()

    repaired = store.get_scene_render_settings(scene["id"])
    assert repaired["large_object_push_enabled"] is False
    assert any(
        entry.get("object_id") == hidden and entry.get("push") == 0.8
        for entry in repaired["custom_object_timing_config"]
    )


def test_malformed_other_visible_push_preserves_existing_activation_flag(tmp_path):
    _app_obj, store, page, scene, first, second = _page(tmp_path)
    store.update_scene_render_settings(
        scene["id"],
        settings={
            "large_object_push_enabled": True,
            "custom_object_timing_config": [
                {"object_id": first, "draw": 0.5, "push": 0.0},
                {"object_id": second, "draw": 0.5, "push": "not-a-number"},
            ],
        },
    )
    page._load_render_controls(scene["id"])
    _select_layer(page, first)
    page.object_push_spin.setValue(0.0)
    page._save_selected_object_timing()

    settings = store.get_scene_render_settings(scene["id"])
    assert settings["large_object_push_enabled"] is True


def test_ui_saved_positive_push_passes_project_export_push_preflight(tmp_path):
    _app_obj, store, page, scene, _first, second = _page(tmp_path)
    _select_layer(page, second)
    page.object_push_spin.setValue(0.25)
    page._save_selected_object_timing()

    media = FakeMediaExporter()
    render_calls = []

    def snapshot(plan, output):
        render_calls.append(("snapshot", plan.scene_id))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    def whiteboard(plan, output, **kwargs):
        render_calls.append((
            "whiteboard",
            plan.scene_id,
            [entry.push for entry in plan.object_timing],
        ))
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).touch()
        return Path(output)

    exporter = ProjectSceneExporter(
        store,
        media_exporter=media,
        snapshot_renderer=snapshot,
        whiteboard_renderer=whiteboard,
    )
    output = exporter.export("p1", tmp_path / "push.mp4")

    assert output == tmp_path / "push.mp4"
    assert render_calls == [("whiteboard", scene["id"], [0.0, 0.25])]
    assert len(media.calls) == 1
