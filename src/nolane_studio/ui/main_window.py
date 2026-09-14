from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from .design import PRODUCT_NAME

SMOKE_FLAG = "--smoke-test"


def default_db_path() -> Path:
    import os

    base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / ".local" / "share"))
    return base / "Nolane Studio" / "studio.db"


def _runtime_args(argv: Sequence[str]) -> tuple[list[str], bool]:
    raw = list(argv)
    smoke = SMOKE_FLAG in raw
    return [arg for arg in raw if arg != SMOKE_FLAG], smoke


def run(argv: Sequence[str] | None = None) -> int:
    """Start the native desktop shell without making Qt a core dependency."""
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for the desktop UI; install nolane-studio[ui]") from exc

    from .qt_window import create_window

    qt_argv, smoke = _runtime_args(sys.argv if argv is None else argv)
    app = QApplication(qt_argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName("Nolane")
    app.setStyle("Fusion")

    smoke_tmp = None
    try:
        if smoke:
            import tempfile
            from imageio_ffmpeg import get_ffmpeg_exe

            smoke_tmp = tempfile.TemporaryDirectory(prefix="nolane-studio-smoke-")
            ffmpeg = Path(get_ffmpeg_exe())
            if not ffmpeg.is_file():
                raise RuntimeError(f"bundled FFmpeg is unavailable: {ffmpeg}")
            window = create_window(db_path=Path(smoke_tmp.name) / "smoke.db")
        else:
            window = create_window()

        window.show()
        if smoke:
            QTimer.singleShot(750, app.quit)
        return int(app.exec())
    finally:
        if smoke_tmp is not None:
            smoke_tmp.cleanup()
