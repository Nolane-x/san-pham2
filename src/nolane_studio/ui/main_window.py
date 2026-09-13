from __future__ import annotations

from pathlib import Path
from typing import Sequence

from .design import PRODUCT_NAME


def default_db_path() -> Path:
    import os

    base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share"))
    return base / "Nolane Studio" / "studio.db"


def run(argv: Sequence[str] | None = None) -> int:
    """Start the native desktop shell without making Qt a core dependency."""
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for the desktop UI; install nolane-studio[ui]") from exc

    from .qt_window import create_window

    app = QApplication(list(argv or []))
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName("Nolane")
    app.setStyle("Fusion")
    window = create_window()
    window.show()
    return int(app.exec())
