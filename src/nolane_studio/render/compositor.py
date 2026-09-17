from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from .scene_plan import SceneRenderPlan


class CompositionError(RuntimeError):
    """Raised when a persisted canvas cannot be represented faithfully."""


class CompositionRequiresVideo(CompositionError):
    """Raised when a scene needs the source-video compositor path."""


_STATIC_VISUAL_KINDS = frozenset({"shape", "text", "image", "drawing"})
_STATIC_GEOMETRY_DEFAULTS = (
    ("x", 0.0),
    ("y", 0.0),
    ("width", 320.0),
    ("height", 180.0),
    ("rotation", 0.0),
)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _bounded_opacity(value: Any) -> float:
    return max(0.0, min(1.0, _float(value, 1.0)))


def _ordered_visible(objects: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(obj) for obj in objects if bool(obj.get("visible", True))),
        key=lambda obj: (int(obj.get("z_index", 0)), str(obj.get("id", ""))),
    )


def _static_payload(raw: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = raw.get("payload")
    return payload if isinstance(payload, Mapping) else {}


def validate_supported_static_visual_geometry(
    plan: SceneRenderPlan,
    *,
    objects: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Reject non-finite visible static-object geometry before rasterization."""
    candidates = plan.objects if objects is None else objects
    for raw in candidates:
        if not bool(raw.get("visible", True)):
            continue
        kind = str(raw.get("kind", "")).strip().lower()
        if kind not in _STATIC_VISUAL_KINDS:
            continue
        object_id = str(raw.get("id", "")).strip()
        for field, default in _STATIC_GEOMETRY_DEFAULTS:
            if not math.isfinite(_float(raw.get(field), default)):
                raise CompositionError(
                    f"scene {plan.scene_id} object {object_id} {field} must be finite"
                )


def validate_supported_static_visual_payload(
    plan: SceneRenderPlan,
    *,
    objects: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Reject persisted static payload values that Qt cannot render faithfully."""
    candidates = plan.objects if objects is None else objects
    for raw in candidates:
        if not bool(raw.get("visible", True)):
            continue
        kind = str(raw.get("kind", "")).strip().lower()
        if kind not in _STATIC_VISUAL_KINDS:
            continue
        object_id = str(raw.get("id", "")).strip()
        payload = _static_payload(raw)

        if kind == "text":
            if not math.isfinite(_float(payload.get("font_size"), 36.0)):
                raise CompositionError(
                    f"scene {plan.scene_id} object {object_id} text font_size must be finite"
                )
            continue

        if kind != "drawing":
            continue

        if not math.isfinite(_float(payload.get("stroke"), 5.0)):
            raise CompositionError(
                f"scene {plan.scene_id} object {object_id} drawing stroke must be finite"
            )

        points = payload.get("points") or []
        if not isinstance(points, (list, tuple)):
            raise CompositionError(
                f"scene {plan.scene_id} object {object_id} drawing points must be coordinate pairs"
            )
        for index, point in enumerate(points):
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                raise CompositionError(
                    f"scene {plan.scene_id} object {object_id} drawing points must be coordinate pairs"
                )
            for axis, component in (("x", point[0]), ("y", point[1])):
                if not math.isfinite(_float(component, 0.0)):
                    raise CompositionError(
                        f"scene {plan.scene_id} object {object_id} drawing point {index} {axis} must be finite"
                    )


def validate_supported_static_visual_state(
    plan: SceneRenderPlan,
    *,
    objects: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    """Preflight all recovered static-object state before any Qt rasterization."""
    validate_supported_static_visual_geometry(plan, objects=objects)
    validate_supported_static_visual_payload(plan, objects=objects)


def render_scene_layer_snapshot(
    plan: SceneRenderPlan,
    output_path: str | Path,
    *,
    objects: Sequence[Mapping[str, Any]],
    transparent: bool,
    width: int = 1280,
    height: int = 720,
    background: str = "#F5F3EC",
) -> Path:
    """Rasterize one ordered static band of a persisted scene.

    Video layers are intentionally rejected here. The source-video compositor
    uses this function for the static bands below and above the video so z-order
    is preserved without flattening or silently dropping a canvas layer.
    """
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen

    width = max(2, int(width))
    height = max(2, int(height))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    ordered = _ordered_visible(objects)
    validate_supported_static_visual_state(plan, objects=ordered)

    video_ids = [
        str(obj.get("id", ""))
        for obj in ordered
        if str(obj.get("kind", "")).strip().lower() == "video"
    ]
    if video_ids:
        raise CompositionRequiresVideo(
            f"scene {plan.scene_id} requires video composition for object(s): {', '.join(video_ids)}"
        )

    image = QImage(width, height, QImage.Format.Format_ARGB32)
    if image.isNull():
        raise CompositionError(f"unable to allocate {width}x{height} scene image")
    image.fill(QColor(0, 0, 0, 0) if transparent else QColor(background))

    painter = QPainter(image)
    if not painter.isActive():
        raise CompositionError("unable to create scene painter")
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    try:
        for obj in ordered:
            kind = str(obj.get("kind", "")).strip().lower()
            if kind not in _STATIC_VISUAL_KINDS:
                raise CompositionError(
                    f"scene {plan.scene_id} contains unsupported visual object kind {kind!r}"
                )

            x = _float(obj.get("x"), 0.0)
            y = _float(obj.get("y"), 0.0)
            object_width = max(0.0, _float(obj.get("width"), 320.0))
            object_height = max(0.0, _float(obj.get("height"), 180.0))
            rotation = _float(obj.get("rotation"), 0.0)
            payload = _static_payload(obj)

            painter.save()
            try:
                painter.setOpacity(_bounded_opacity(obj.get("opacity", 1.0)))
                painter.translate(x, y)
                painter.rotate(rotation)
                rect = QRectF(0.0, 0.0, object_width, object_height)

                if kind == "shape":
                    painter.setPen(QPen(QColor("#687087"), 1.5))
                    painter.setBrush(QColor(str(payload.get("fill", "#DDD9CD"))))
                    painter.drawRoundedRect(rect, 8.0, 8.0)
                    continue

                if kind == "text":
                    painter.setPen(QColor(str(payload.get("color", "#20232A"))))
                    font = QFont()
                    font.setPixelSize(max(8, int(_float(payload.get("font_size"), 36))))
                    painter.setFont(font)
                    painter.drawText(
                        rect.adjusted(6.0, 4.0, -6.0, -4.0),
                        int(Qt.TextFlag.TextWordWrap),
                        str(payload.get("text", "Text")),
                    )
                    continue

                if kind == "image":
                    source = Path(str(obj.get("source") or ""))
                    if not source.is_file():
                        raise FileNotFoundError(f"scene image source not found: {source}")
                    source_image = QImage(str(source))
                    if source_image.isNull():
                        raise CompositionError(f"unable to decode scene image: {source}")
                    painter.drawImage(rect, source_image)
                    continue

                points = payload.get("points") or []
                if len(points) < 2:
                    continue
                first = points[0]
                path = QPainterPath(QPointF(_float(first[0], 0.0), _float(first[1], 0.0)))
                for point in points[1:]:
                    path.lineTo(_float(point[0], 0.0), _float(point[1], 0.0))
                painter.setPen(
                    QPen(
                        QColor(str(payload.get("color", "#20232A"))),
                        max(0.1, _float(payload.get("stroke"), 5.0)),
                        Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin,
                    )
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)
            finally:
                painter.restore()
    finally:
        painter.end()

    if not image.save(str(output)):
        raise CompositionError(f"unable to save scene snapshot: {output}")
    return output


def render_scene_snapshot(
    plan: SceneRenderPlan,
    output_path: str | Path,
    *,
    width: int = 1280,
    height: int = 720,
    background: str = "#F5F3EC",
) -> Path:
    """Rasterize a persisted scene without dropping static canvas layers."""
    ordered = _ordered_visible(plan.objects)
    video_ids = [
        str(obj.get("id", ""))
        for obj in ordered
        if str(obj.get("kind", "")).strip().lower() == "video"
    ]
    if video_ids:
        raise CompositionRequiresVideo(
            f"scene {plan.scene_id} requires video composition for object(s): {', '.join(video_ids)}"
        )
    return render_scene_layer_snapshot(
        plan,
        output_path,
        objects=ordered,
        transparent=False,
        width=width,
        height=height,
        background=background,
    )
