from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..app import build_services
from ..config import SettingsStore
from ..storage.store import ProjectStore
from .design import NAV_ITEMS, PRODUCT_NAME, qss
from .main_window import default_db_path
from .pages import CreatePage, LibraryPage, ProvidersPage, StudioPage
from .widgets import BrandMark, NavButton


class MainWindow(QMainWindow):
    def __init__(self, store: ProjectStore, providers, settings_store: SettingsStore) -> None:
        super().__init__()
        self.setWindowTitle(PRODUCT_NAME)
        self.resize(1440, 900)
        self.setMinimumSize(1120, 720)

        root = QWidget(self)
        root.setObjectName("appRoot")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame(root)
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 16, 14, 14)
        side.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(BrandMark())
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel(PRODUCT_NAME)
        name.setObjectName("brandName")
        meta = QLabel("CREATIVE SYSTEM")
        meta.setObjectName("brandMeta")
        brand_text.addWidget(name)
        brand_text.addWidget(meta)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        side.addLayout(brand_row)
        side.addSpacing(16)

        self.nav_buttons: list[NavButton] = []
        for idx, item in enumerate(NAV_ITEMS):
            button = NavButton(item.label)
            button.setToolTip(item.eyebrow.title())
            button.clicked.connect(lambda checked=False, i=idx: self._navigate(i))
            side.addWidget(button)
            self.nav_buttons.append(button)
        side.addStretch(1)

        new_btn = QPushButton("+ New project")
        new_btn.setObjectName("primary")
        new_btn.clicked.connect(lambda: self._navigate(0))
        side.addWidget(new_btn)
        local = QLabel("LOCAL-FIRST")
        local.setObjectName("brandMeta")
        local.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(local)

        self.pages = QStackedWidget(root)
        self.create_page = CreatePage(store)
        self.studio_page = StudioPage(store, providers=providers)
        self.library_page = LibraryPage(store)
        self.providers_page = ProvidersPage(providers.descriptors, settings_store)
        self.pages.addWidget(self.create_page)
        self.pages.addWidget(self.studio_page)
        self.pages.addWidget(self.library_page)
        self.pages.addWidget(self.providers_page)

        self.create_page.project_created.connect(self._on_project_created)
        self.library_page.open_project.connect(self._open_existing_project)
        self.studio_page.status_message.connect(self._show_status)
        self.providers_page.status_message.connect(self._show_status)

        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready · local workspace")
        self._navigate(0)

    def _navigate(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        if index == 2:
            self.library_page.refresh()

    def _on_project_created(self, project_id: str, title: str, scenes: list) -> None:
        self.studio_page.load_project(project_id, title, scenes)
        self.statusBar().showMessage(f"Created {title} · {len(scenes) or 1} scene(s)", 5000)
        self._navigate(1)

    def _open_existing_project(self, project_id: str, title: str) -> None:
        self.studio_page.load_project(project_id, title, [])
        self._navigate(1)

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)


def create_window(*, db_path=None) -> MainWindow:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication must exist before creating the window")
    app.setStyleSheet(qss())
    store = ProjectStore(db_path or default_db_path())
    store.initialize()
    settings_store = SettingsStore()
    services = build_services(settings_store.load())
    return MainWindow(store, services.providers, settings_store)
