from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui.pages import StudioPage


def test_selected_scene_text_can_be_edited_and_persisted(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Demo")
    store.replace_scenes("p1", [Scene(0, "Original"), Scene(1, "Second")])

    page = StudioPage(store)
    page.load_project("p1", "Demo", [])
    page.scenes.setCurrentRow(0)

    assert page.scene_text_edit.toPlainText() == "Original"
    page.scene_text_edit.setPlainText("Edited scene text")
    page._save_selected_scene()

    assert [scene["text"] for scene in store.list_scenes("p1")] == ["Edited scene text", "Second"]
    assert page.scenes.item(0).text() == "01  Edited scene text"
