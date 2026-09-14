from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import CreatePage, StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _store(tmp_path) -> ProjectStore:
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    return store


def _timeline_labels(page: StudioPage) -> list[str]:
    return [
        label.text()
        for label in page.findChildren(QLabel)
        if label.text().startswith("Scene ")
    ]


def test_create_page_persists_generated_scene_plan_before_emitting(tmp_path):
    _app()
    store = _store(tmp_path)
    page = CreatePage(store)
    page.title_edit.setText("Persisted plan")
    emitted = []
    page.project_created.connect(lambda project_id, title, scenes: emitted.append((project_id, title, scenes)))

    scenes = [Scene(0, "Opening"), Scene(1, "Closing")]
    page._persist_and_emit(scenes)

    project_id = emitted[0][0]
    persisted = store.list_scenes(project_id)
    assert [scene["text"] for scene in persisted] == ["Opening", "Closing"]
    assert store.get_project(project_id)["expected_image_count"] == 2


def test_studio_reopens_persisted_scenes_and_timeline_from_single_source(tmp_path):
    _app()
    store = _store(tmp_path)
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Opening"), Scene(1, "Middle"), Scene(2, "Closing")])
    page = StudioPage(store)

    page.load_project("p1", "Demo", [])

    assert page.scenes.count() == 3
    assert [page.scenes.item(i).text() for i in range(3)] == ["01  Opening", "02  Middle", "03  Closing"]
    persisted_ids = [scene["id"] for scene in store.list_scenes("p1")]
    assert [page.scenes.item(i).data(Qt.ItemDataRole.UserRole) for i in range(3)] == persisted_ids
    assert _timeline_labels(page) == ["Scene 1", "Scene 2", "Scene 3"]


def test_studio_scene_crud_updates_storage_list_and_timeline_together(tmp_path):
    _app()
    store = _store(tmp_path)
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "One"), Scene(1, "Two")])
    page = StudioPage(store)
    page.load_project("p1", "Demo", [])

    page.scenes.setCurrentRow(0)
    page._duplicate_selected_scene()
    assert [scene["text"] for scene in store.list_scenes("p1")] == ["One", "One copy", "Two"]
    assert _timeline_labels(page) == ["Scene 1", "Scene 2", "Scene 3"]

    page._move_selected_scene(1)
    assert [scene["text"] for scene in store.list_scenes("p1")] == ["One", "Two", "One copy"]

    page._delete_selected_scene()
    assert [scene["text"] for scene in store.list_scenes("p1")] == ["One", "Two"]
    assert page.scenes.count() == 2
    assert _timeline_labels(page) == ["Scene 1", "Scene 2"]

    page._add_scene()
    assert [scene["text"] for scene in store.list_scenes("p1")] == ["One", "Two", "New scene"]
    assert page.scenes.currentRow() == 2
    assert _timeline_labels(page) == ["Scene 1", "Scene 2", "Scene 3"]
