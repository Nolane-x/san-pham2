from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

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


class CanvasPreview(QWidget):
    """Low-cost authored canvas placeholder; no external or legacy assets."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tokens = ThemeTokens()
        self.setMinimumSize(520, 300)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(18, 18, -18, -18)
        ratio = 16 / 9
        w = area.width()
        h = int(w / ratio)
        if h > area.height():
            h = area.height()
            w = int(h * ratio)
        x = area.center().x() - w // 2
        y = area.center().y() - h // 2
        canvas = QRectF(x, y, w, h)
        p.setPen(QPen(QColor("#2D3343"), 1))
        p.setBrush(QColor("#F5F3EC"))
        p.drawRoundedRect(canvas, 4, 4)

        # Signature scene: editorial frame, motion path and subject blocks.
        accent = QColor(self.tokens.accent_primary)
        ink = QColor("#20232A")
        p.setPen(QPen(ink, max(2.0, w / 240)))
        p.drawLine(QPointF(x + w * 0.12, y + h * 0.24), QPointF(x + w * 0.57, y + h * 0.24))
        p.setPen(QPen(QColor("#9A9A95"), max(1.0, w / 420)))
        p.drawLine(QPointF(x + w * 0.12, y + h * 0.33), QPointF(x + w * 0.46, y + h * 0.33))
        p.drawLine(QPointF(x + w * 0.12, y + h * 0.38), QPointF(x + w * 0.40, y + h * 0.38))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#DDD9CD"))
        p.drawRoundedRect(QRectF(x + w * 0.60, y + h * 0.18, w * 0.25, h * 0.45), 12, 12)
        p.setBrush(accent)
        p.drawEllipse(QRectF(x + w * 0.68, y + h * 0.28, w * 0.09, w * 0.09))
        p.setPen(QPen(accent, max(2.0, w / 260), Qt.PenStyle.DashLine))
        p.drawCubicBezier(
            QPointF(x + w * 0.15, y + h * 0.72),
            QPointF(x + w * 0.42, y + h * 0.50),
            QPointF(x + w * 0.59, y + h * 0.87),
            QPointF(x + w * 0.80, y + h * 0.70),
        )
        p.end()
