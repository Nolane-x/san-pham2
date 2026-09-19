from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.render.project_export import ProjectSceneExporter
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui import pages as pages_module
from nolane_studio.ui.pages import StudioPage


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_preview_toolbar_action_uses_selected_scene_preview_and_opens_result(
    tmp_path: Path,
    monkeypatch,
):
    app = _app()
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Preview UI")
    store.replace_scenes("p1", [Scene(0, "Selected scene")])
    scene = store.list_scenes("p1")[0]

    calls = []

    def fake_preview(self, project_id, scene_id, output, **kwargs):
        del self, kwargs
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        calls.append((project_id, scene_id, path))
        return path

    opened = []
    monkeypatch.setattr(ProjectSceneExporter, "preview_scene", fake_preview)
    monkeypatch.setattr(
        pages_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )

    page = StudioPage(store)
    page.load_project("p1", "Preview UI", [])
    assert page.preview_button.text() == "Preview"
    assert "selected scene" in page.preview_button.toolTip().lower()

    page.preview_button.click()
    workers = list(page._task_workers)
    assert len(workers) == 1
    assert workers[0].wait(3000)
    app.processEvents()

    assert calls
    assert calls[0][0] == "p1"
    assert calls[0][1] == scene["id"]
    assert calls[0][2].name == f"p1-{scene['id']}.mp4"
    assert opened == [str(calls[0][2].resolve())]
