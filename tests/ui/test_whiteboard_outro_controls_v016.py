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


def _page(tmp_path: Path, *, settings: dict | None = None):
    app = _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Outro")
    store.replace_scenes("p1", [Scene(0, "Scene")])
    scene = store.list_scenes("p1")[0]
    if settings is not None:
        store.update_scene_render_settings(scene["id"], settings=settings)
    page = StudioPage(store)
    page.load_project("p1", "Outro", [])
    app.processEvents()
    return app, store, page, scene


def test_whiteboard_outro_controls_persist_recovered_left_contract(tmp_path):
    app, store, page, scene = _page(tmp_path)

    assert page.render_style_combo.currentData() == "whiteboard"
    assert page.outro_enabled_check.isEnabled()
    assert page.outro_direction_combo.currentData() == "left"

    page.outro_enabled_check.setChecked(True)
    page.outro_duration_spin.setValue(0.4)
    page.save_scene_button.click()
    app.processEvents()

    settings = store.get_scene_render_settings(scene["id"])
    assert settings["outro_enabled"] is True
    assert settings["outro_direction"] == "left"
    assert settings["outro_duration"] == 0.4


def test_outro_controls_preserve_unknown_direction_until_user_selects_verified_left(tmp_path):
    app, store, page, scene = _page(
        tmp_path,
        settings={
            "style": "whiteboard",
            "outro_enabled": True,
            "outro_direction": "diagonal",
            "outro_duration": 0.45,
        },
    )

    assert page.outro_enabled_check.isChecked() is True
    assert page.outro_direction_combo.currentData() == "diagonal"
    assert "unsupported" in page.outro_direction_combo.currentText().lower()

    page.save_scene_button.click()
    app.processEvents()
    preserved = store.get_scene_render_settings(scene["id"])
    assert preserved["outro_direction"] == "diagonal"

    page.outro_direction_combo.setCurrentIndex(
        page.outro_direction_combo.findData("left")
    )
    page.save_scene_button.click()
    app.processEvents()
    repaired = store.get_scene_render_settings(scene["id"])
    assert repaired["outro_direction"] == "left"


def test_outro_controls_are_not_creatable_for_color_reveal(tmp_path):
    app, _store, page, _scene = _page(
        tmp_path,
        settings={"style": "color_reveal"},
    )

    assert page.render_style_combo.currentData() == "color_reveal"
    assert page.outro_enabled_check.isEnabled() is False
    assert page.outro_direction_combo.isEnabled() is False
    assert page.outro_duration_spin.isEnabled() is False
    assert "whiteboard" in page.outro_enabled_check.toolTip().lower()

    page.render_style_combo.setCurrentIndex(
        page.render_style_combo.findData("whiteboard")
    )
    app.processEvents()
    assert page.outro_enabled_check.isEnabled() is True
