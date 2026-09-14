from __future__ import annotations

import argparse
import os
import platform
import tempfile
from collections.abc import MutableMapping
from pathlib import Path


def configure_capture_environment(environ: MutableMapping[str, str], system_name: str) -> None:
    """Use native Windows font/render plumbing; offscreen only where a display is unavailable."""
    if system_name != "Windows":
        environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    configure_capture_environment(os.environ, platform.system())
    from PySide6.QtWidgets import QApplication

    from nolane_studio.domain import Scene
    from nolane_studio.ui.design import PRODUCT_NAME
    from nolane_studio.ui.qt_window import create_window

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(PRODUCT_NAME)

    with tempfile.TemporaryDirectory(prefix="nolane-ui-capture-") as tmp:
        window = create_window(db_path=Path(tmp) / "capture.db")
        window.resize(1440, 900)
        window.show()
        app.processEvents()
        if not window.grab().save(str(output / "create.png"), "PNG"):
            raise RuntimeError("failed to save create screenshot")

        demo_scenes = [
            Scene(0, "Open with a clear promise and one visual idea that can be drawn without clutter."),
            Scene(1, "Move into the main explanation while the canvas keeps focus on the current concept."),
            Scene(2, "Close with a compact visual summary and a clean call to action."),
        ]
        window.studio_page.store.create_project("preview", "Launch story")
        window.studio_page.load_project("preview", "Launch story", demo_scenes)
        window._navigate(1)
        app.processEvents()
        if not window.grab().save(str(output / "studio.png"), "PNG"):
            raise RuntimeError("failed to save studio screenshot")
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
