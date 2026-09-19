from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .design import ThemeTokens


class BrandMark(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(34, 34)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, 31, 31)
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        grad = QLinearGradient(QPointF(3, 3), QPointF(31, 31))
        grad.setColorAt(0.0, QColor("#9D91FF"))
        grad.setColorAt(0.55, QColor("#796BFF"))
        grad.setColorAt(1.0, QColor("#4ED7C5"))
        p.fillPath(path, grad)
        p.setPen(QPen(QColor("#0A0B0F"), 3.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(10.5, 23.0), QPointF(10.5, 11.0))
        p.drawLine(QPointF(10.5, 11.0), QPointF(23.0, 23.0))
        p.drawLine(QPointF(23.0, 23.0), QPointF(23.0, 11.0))
        p.end()


class NavButton(QPushButton):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Surface(QFrame):
    def __init__(self, *, raised: bool = False, accent: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("accentSurface" if accent else ("surfaceRaised" if raised else "surface"))


class SectionTitle(QWidget):
    def __init__(self, eyebrow: str, title: str, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        eye = QLabel(eyebrow.upper())
        eye.setObjectName("eyebrow")
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(eye)
        layout.addWidget(heading)
        if description:
            body = QLabel(description)
            body.setObjectName("muted")
            body.setWordWrap(True)
            layout.addWidget(body)


class Dot(QWidget):
    def __init__(self, color: str, size: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(self.rect())
        p.end()


class _CanvasObjectItem(QGraphicsItem):
    def __init__(self, owner: "CanvasEditor", model: dict[str, Any]) -> None:
        super().__init__()
        self.owner = owner
        self.model = dict(model)
        self.object_id = str(model["id"])
        self.kind = str(model.get("kind", "shape"))
        self.payload = dict(model.get("payload") or {})
        self._width = float(model.get("width", 320.0))
        self._height = float(model.get("height", 180.0))
        self.source = str(model.get("source") or "")
        self.setPos(float(model.get("x", 0.0)), float(model.get("y", 0.0)))
        self.setRotation(float(model.get("rotation", 0.0)))
        self.setOpacity(float(model.get("opacity", 1.0)))
        self.setZValue(float(model.get("z_index", 0)))
        locked = bool(model.get("locked", False))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not locked)
        self.setCursor(Qt.CursorShape.ArrowCursor if locked else Qt.CursorShape.SizeAllCursor)
        self._pixmap = QPixmap()
        if self.kind == "image" and self.source and Path(self.source).is_file():
            self._pixmap = QPixmap(self.source)

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        return QRectF(0.0, 0.0, self._width, self._height)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802 - Qt API
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.boundingRect()
        if self.kind == "image" and not self._pixmap.isNull():
            painter.drawPixmap(rect.toRect(), self._pixmap)
        elif self.kind == "text":
            painter.setPen(QColor(str(self.payload.get("color", "#20232A"))))
            font = QFont()
            font.setPixelSize(max(8, int(self.payload.get("font_size", 36))))
            painter.setFont(font)
            painter.drawText(rect.adjusted(6, 4, -6, -4), Qt.TextFlag.TextWordWrap, str(self.payload.get("text", "Text")))
        elif self.kind == "drawing":
            painter.setPen(
                QPen(
                    QColor(str(self.payload.get("color", "#20232A"))),
                    float(self.payload.get("stroke", 5)),
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            points = self.payload.get("points") or []
            if len(points) >= 2:
                path = QPainterPath(QPointF(float(points[0][0]), float(points[0][1])))
                for point in points[1:]:
                    path.lineTo(float(point[0]), float(point[1]))
                painter.drawPath(path)
        else:
            fill = "#DDD9CD" if self.kind == "shape" else "#272B37"
            painter.setPen(QPen(QColor("#687087"), 1.5))
            painter.setBrush(QColor(str(self.payload.get("fill", fill))))
            painter.drawRoundedRect(rect, 8, 8)
            if self.kind == "video":
                painter.setPen(QColor("#F5F7FB"))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "VIDEO")
        if self.isSelected():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#796BFF"), 3, Qt.PenStyle.SolidLine))
            painter.drawRect(rect.adjusted(1.5, 1.5, -1.5, -1.5))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().mouseReleaseEvent(event)
        self.owner._emit_transform(self)


class _CanvasGraphicsView(QGraphicsView):
    """View that routes pointer strokes to CanvasEditor only while draw mode is active."""

    def __init__(self, scene: QGraphicsScene, owner: "CanvasEditor") -> None:
        super().__init__(scene, owner)
        self.owner = owner

    def _scene_point(self, event) -> QPointF:
        return self.mapToScene(event.position().toPoint())

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self.owner.drawing_enabled and event.button() == Qt.MouseButton.LeftButton:
            point = self._scene_point(event)
            self.owner.begin_stroke(point.x(), point.y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self.owner.drawing_enabled
            and self.owner.stroke_active
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            point = self._scene_point(event)
            self.owner.append_stroke_point(point.x(), point.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self.owner.drawing_enabled
            and self.owner.stroke_active
            and event.button() == Qt.MouseButton.LeftButton
        ):
            point = self._scene_point(event)
            self.owner.append_stroke_point(point.x(), point.y())
            self.owner.finish_stroke()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CanvasEditor(QWidget):
    """Persistent 1280x720 scene composition surface used by the rebuilt visual editor."""

    object_selected = Signal(str)
    object_transform_changed = Signal(str, float, float, float, float, float)
    drawing_completed = Signal(list)

    CANVAS_WIDTH = 1280.0
    CANVAS_HEIGHT = 720.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(520, 300)
        self._graphics_scene = QGraphicsScene(self)
        self._graphics_scene.setSceneRect(0, 0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT)
        self._graphics_scene.setBackgroundBrush(QColor("#F5F3EC"))
        self._view = _CanvasGraphicsView(self._graphics_scene, self)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        self._items: dict[str, _CanvasObjectItem] = {}
        self._ordered_ids: list[str] = []
        self._drawing_enabled = False
        self._stroke_points: list[tuple[float, float]] = []
        self._stroke_preview: QGraphicsPathItem | None = None
        self._graphics_scene.selectionChanged.connect(self._selection_changed)

    @property
    def drawing_enabled(self) -> bool:
        return self._drawing_enabled

    @property
    def stroke_active(self) -> bool:
        return bool(self._stroke_points)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit_canvas()

    def showEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        self._fit_canvas()

    def _fit_canvas(self) -> None:
        self._view.fitInView(self._graphics_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_drawing_enabled(self, enabled: bool) -> None:
        self._drawing_enabled = bool(enabled)
        if not self._drawing_enabled:
            self.cancel_stroke()
        self._view.viewport().setCursor(
            Qt.CursorShape.CrossCursor if self._drawing_enabled else Qt.CursorShape.ArrowCursor
        )

    @classmethod
    def _clamped_point(cls, x: float, y: float) -> tuple[float, float]:
        return (
            max(0.0, min(cls.CANVAS_WIDTH, float(x))),
            max(0.0, min(cls.CANVAS_HEIGHT, float(y))),
        )

    def begin_stroke(self, x: float, y: float) -> None:
        if not self._drawing_enabled:
            return
        self.cancel_stroke()
        self._stroke_points = [self._clamped_point(x, y)]
        self._update_stroke_preview()

    def append_stroke_point(self, x: float, y: float) -> None:
        if not self._drawing_enabled or not self._stroke_points:
            return
        point = self._clamped_point(x, y)
        if point == self._stroke_points[-1]:
            return
        self._stroke_points.append(point)
        self._update_stroke_preview()

    def finish_stroke(self) -> None:
        if not self._drawing_enabled or not self._stroke_points:
            return
        points = list(self._stroke_points)
        self._clear_stroke_preview()
        self._stroke_points = []
        if len(points) >= 2:
            self.drawing_completed.emit(points)

    def cancel_stroke(self) -> None:
        self._stroke_points = []
        self._clear_stroke_preview()

    def _update_stroke_preview(self) -> None:
        if not self._stroke_points:
            return
        first = self._stroke_points[0]
        path = QPainterPath(QPointF(first[0], first[1]))
        for x, y in self._stroke_points[1:]:
            path.lineTo(x, y)
        if self._stroke_preview is None:
            self._stroke_preview = QGraphicsPathItem()
            self._stroke_preview.setZValue(1_000_000)
            self._stroke_preview.setPen(
                QPen(
                    QColor("#20232A"),
                    5.0,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin,
                )
            )
            self._graphics_scene.addItem(self._stroke_preview)
        self._stroke_preview.setPath(path)

    def _clear_stroke_preview(self) -> None:
        if self._stroke_preview is not None:
            if self._stroke_preview.scene() is self._graphics_scene:
                self._graphics_scene.removeItem(self._stroke_preview)
            self._stroke_preview = None

    @staticmethod
    def _validated_z_index(model: Mapping[str, Any]) -> int:
        object_id = str(model.get("id", "")).strip()
        value = model.get("z_index", 0)
        try:
            if isinstance(value, float):
                if not math.isfinite(value) or not value.is_integer():
                    raise ValueError
                index = int(value)
            elif isinstance(value, (int, str)):
                index = int(value)
            else:
                index = int(value)
                if value != index:
                    raise ValueError
        except (TypeError, ValueError, OverflowError):
            raise ValueError(
                f"visual object {object_id} z_index must be a non-negative integer"
            ) from None
        if index < 0:
            raise ValueError(
                f"visual object {object_id} z_index must be a non-negative integer"
            )
        return index

    @classmethod
    def _preflight_model(cls, model: Mapping[str, Any]) -> int:
        object_id = str(model.get("id", "")).strip()
        index = cls._validated_z_index(model)
        payload = model.get("payload")
        if payload is not None and not isinstance(payload, Mapping):
            raise ValueError(f"visual object {object_id} payload must be a mapping")
        return index

    def set_objects(self, objects: list[dict[str, Any]]) -> None:
        indexed = [(self._preflight_model(model), model) for model in objects]
        ordered = [
            model
            for _, model in sorted(
                indexed,
                key=lambda pair: (pair[0], str(pair[1].get("id", ""))),
            )
        ]

        self.cancel_stroke()
        self._graphics_scene.clear()
        self._stroke_preview = None
        self._items.clear()
        self._ordered_ids = [str(row["id"]) for row in ordered]
        for model in ordered:
            if not bool(model.get("visible", True)):
                continue
            item = _CanvasObjectItem(self, model)
            self._graphics_scene.addItem(item)
            self._items[item.object_id] = item
        self._fit_canvas()

    def object_ids(self) -> list[str]:
        return list(self._ordered_ids)

    def object_count(self) -> int:
        return len(self._ordered_ids)

    def object_geometry(self, object_id: str) -> tuple[float, float, float, float, float]:
        item = self._items[object_id]
        rect = item.boundingRect()
        return (item.pos().x(), item.pos().y(), rect.width(), rect.height(), item.rotation())

    def select_object(self, object_id: str | None) -> None:
        self._graphics_scene.clearSelection()
        if object_id and object_id in self._items:
            self._items[object_id].setSelected(True)
            self._view.ensureVisible(self._items[object_id])

    def _selection_changed(self) -> None:
        selected = self._graphics_scene.selectedItems()
        if selected and isinstance(selected[0], _CanvasObjectItem):
            self.object_selected.emit(selected[0].object_id)

    def _emit_transform(self, item: _CanvasObjectItem) -> None:
        rect = item.boundingRect()
        self.object_transform_changed.emit(
            item.object_id,
            float(item.pos().x()),
            float(item.pos().y()),
            float(rect.width()),
            float(rect.height()),
            float(item.rotation()),
        )


class CanvasPreview(CanvasEditor):
    """Compatibility name retained while the real object-backed canvas replaces the old placeholder."""
