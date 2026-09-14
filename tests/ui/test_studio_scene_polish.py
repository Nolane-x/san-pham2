from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _studio(tmp_path) -> StudioPage:
    _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo", expected_image_count=3)
    return StudioPage(store)


def test_scene_list_uses_elision_without_horizontal_scrolling(tmp_path):
    page = _studio(tmp_path)

    assert page.scenes.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert page.scenes.textElideMode() == Qt.TextElideMode.ElideRight


def test_timeline_tracks_loaded_project_scenes(tmp_path):
    page = _studio(tmp_path)
    scenes = [
        SimpleNamespace(index=0, text="Opening scene"),
        SimpleNamespace(index=1, text="Middle scene"),
        SimpleNamespace(index=2, text="Closing scene"),
    ]

    page.load_project("p1", "Demo", scenes)

    labels = [
        label.text()
        for label in page.findChildren(QLabel)
        if label.text().startswith("Scene ")
    ]
    assert labels == ["Scene 1", "Scene 2", "Scene 3"]
