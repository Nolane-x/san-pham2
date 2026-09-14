from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_canvas_preview_renders_without_qt_painter_errors():
    from PySide6.QtWidgets import QApplication

    from nolane_studio.ui.widgets import CanvasPreview

    app = QApplication.instance() or QApplication([])
    widget = CanvasPreview()
    widget.resize(900, 560)
    widget.show()
    app.processEvents()

    pixmap = widget.grab()

    assert not pixmap.isNull()
    assert pixmap.width() == 900
    assert pixmap.height() == 560
