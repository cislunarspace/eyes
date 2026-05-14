"""icon_factory — QPainter-generated almond eye icons for tray and window."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap

from .types import TrayIconState

ICON_SIZES = (16, 32, 48, 256)
PUPIL_COLOR = QColor("#222222")
_OUTLINE_COLOR = QColor("#222222")
_PUPIL_RADIUS_RATIO = 0.15


def create_eye_icon(state: TrayIconState) -> QIcon:
    icon = QIcon()
    for size in ICON_SIZES:
        pm = _draw_eye(state, size)
        icon.addPixmap(pm)
    return icon


def _draw_eye(state: TrayIconState, size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(QColor("transparent"))

    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    margin = max(1, size // 10)
    rect = QRect(margin, margin, size - 2 * margin, size - 2 * margin)

    pen = QPen(_OUTLINE_COLOR, max(1, size // 20))
    painter.setPen(pen)
    painter.setBrush(QBrush(QColor("transparent")))

    painter.drawEllipse(rect)

    if state == TrayIconState.ACTIVE:
        _draw_pupil(painter, rect, 0)
    elif state == TrayIconState.PAUSED:
        _draw_pupil(painter, rect, 0.25)
    elif state == TrayIconState.UNAVAILABLE:
        _draw_closed_lid(painter, rect)

    painter.end()
    return pm


def _draw_pupil(painter: QPainter, rect: QRect, x_offset_ratio: float) -> None:
    r = max(1, int(rect.width() * _PUPIL_RADIUS_RATIO))
    cx = rect.x() + rect.width() // 2 + int(rect.width() * x_offset_ratio)
    cy = rect.y() + rect.height() // 2
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(PUPIL_COLOR))
    painter.drawEllipse(QRect(cx - r, cy - r, 2 * r, 2 * r))


def _draw_closed_lid(painter: QPainter, rect: QRect) -> None:
    cy = rect.y() + rect.height() // 2
    pen = QPen(_OUTLINE_COLOR, max(1, rect.width() // 10))
    painter.setPen(pen)
    painter.drawLine(rect.x() + rect.width() // 4, cy, rect.x() + 3 * rect.width() // 4, cy)
