from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from nolane_studio.domain import Scene
from nolane_studio.storage.store import ProjectStore
from nolane_studio.ui import pages


class _SignalStub:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class _WorkerStub:
    created = []

    def __init__(self, store, project_id, output_path, parent=None):
        self.store = store
        self.project_id = project_id
        self.output_path = output_path
        self.parent = parent
        self.completed = _SignalStub()
        self.failed = _SignalStub()
        self.started = False
        type(self).created.append(self)

    def start(self):
        self.started = True


def _page(tmp_path):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "studio.db")
    store.initialize()
    store.create_project("p1", "Canvas-only export")
    store.replace_scenes("p1", [Scene(0, "Opening")])
    scene_id = store.list_scenes("p1")[0]["id"]
    store.add_visual_object(scene_id, "shape", name="Card", payload={"fill": "#FF0000"})
    page = pages.StudioPage(store)
    page.load_project("p1", "Canvas-only export", [])
    return store, page


def test_export_worker_routes_persisted_project_to_project_scene_exporter(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    store = ProjectStore(tmp_path / "worker.db")
    store.initialize()
    store.create_project("p1", "Worker")
    output = tmp_path / "worker.mp4"
    calls = []

    class FakeProjectSceneExporter:
        def __init__(self, actual_store):
            assert actual_store is store

        def export(self, project_id, output_path):
            calls.append((project_id, Path(output_path)))
            return Path(output_path)

    monkeypatch.setattr(pages, "ProjectSceneExporter", FakeProjectSceneExporter, raising=False)
    worker = pages.ExportWorker(store, "p1", str(output))
    worker.run()

    assert calls == [("p1", output)]


def test_studio_export_accepts_canvas_only_project_without_loose_media(tmp_path, monkeypatch):
    store, page = _page(tmp_path)
    output = tmp_path / "canvas-only.mp4"
    _WorkerStub.created.clear()
    statuses = []
    page.status_message.connect(statuses.append)

    monkeypatch.setattr(pages.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(output), "MP4 video (*.mp4)"))
    monkeypatch.setattr(pages, "ExportWorker", _WorkerStub)

    page._export_media()

    assert len(_WorkerStub.created) == 1
    worker = _WorkerStub.created[0]
    assert worker.store is store
    assert worker.project_id == "p1"
    assert worker.output_path == str(output)
    assert worker.started
    assert not page.export_button.isEnabled()
    assert page.export_button.text() == "Exporting…"
    assert any("scene" in status.lower() or "canvas" in status.lower() for status in statuses)
    assert all("import at least one" not in status.lower() for status in statuses)
