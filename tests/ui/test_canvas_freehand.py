from __future__ import annotations

# TDD RED sentinel: CanvasEditor intentionally lacks this freehand API at this commit.
from PySide6.QtWidgets import QApplication

from nolane_studio.ui.widgets import CanvasEditor


def _canvas():
    QApplication.instance() or QApplication([])
    return CanvasEditor()


def test_freehand_stroke_emits_deterministic_canvas_points():
    canvas = _canvas()
    completed: list[list[tuple[float, float]]] = []
    canvas.drawing_completed.connect(completed.append)

    canvas.set_drawing_enabled(True)
    canvas.begin_stroke(10, 20)
    canvas.append_stroke_point(30, 40)
    canvas.append_stroke_point(30, 40)
    canvas.append_stroke_point(1500, -50)
    canvas.finish_stroke()

    assert completed == [[(10.0, 20.0), (30.0, 40.0), (1280.0, 0.0)]]


def test_freehand_is_inert_when_drawing_mode_is_disabled():
    canvas = _canvas()
    completed: list[list[tuple[float, float]]] = []
    canvas.drawing_completed.connect(completed.append)

    canvas.begin_stroke(10, 20)
    canvas.append_stroke_point(30, 40)
    canvas.finish_stroke()

    assert completed == []


def test_short_or_cancelled_freehand_strokes_are_not_persisted():
    canvas = _canvas()
    completed: list[list[tuple[float, float]]] = []
    canvas.drawing_completed.connect(completed.append)
    canvas.set_drawing_enabled(True)

    canvas.begin_stroke(10, 20)
    canvas.finish_stroke()
    canvas.begin_stroke(20, 30)
    canvas.append_stroke_point(40, 50)
    canvas.cancel_stroke()

    assert completed == []
