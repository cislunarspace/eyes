"""Tests for icon_factory — QPainter-generated almond eye icons."""

from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPixmap

from eyes.icon_factory import ICON_SIZES, PUPIL_COLOR, create_eye_icon
from eyes.types import TrayIconState


class TestCreateEyeIcon:
    """Verify create_eye_icon returns valid QIcon for each state."""

    def test_returns_qicon_for_active(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.ACTIVE)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_returns_qicon_for_paused(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.PAUSED)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_returns_qicon_for_unavailable(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.UNAVAILABLE)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()

    def test_icon_has_pixmaps_at_all_sizes(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.ACTIVE)
        for size in ICON_SIZES:
            pm = icon.pixmap(size)
            assert not pm.isNull(), f"Missing pixmap at size {size}"
            dpr = pm.devicePixelRatio()
            assert pm.width() / dpr == size
            assert pm.height() / dpr == size


def _pixel_color(pm: QPixmap, x: int, y: int) -> QColor:
    img = pm.toImage()
    return QColor(img.pixelColor(x, y))


class TestActiveIcon:
    """ACTIVE state: almond shape with centered pupil."""

    def test_center_pixel_is_pupil_color(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.ACTIVE)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        color = _pixel_color(pm, cx, cy)
        assert color == PUPIL_COLOR

    def test_center_pixel_is_white_in_dark_mode(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.ACTIVE, dark_mode=True)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        assert _pixel_color(pm, cx, cy) == QColor("#FFFFFF")


class TestPausedIcon:
    """PAUSED state: almond shape with pupil shifted right of center."""

    def test_pupil_is_right_of_center(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.PAUSED)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        # At center should NOT be pupil
        assert _pixel_color(pm, cx, cy) != PUPIL_COLOR
        # Right of center should be pupil
        offset_x = int(cx + pm.width() / dpr * 0.15 * dpr)
        assert _pixel_color(pm, offset_x, cy) == PUPIL_COLOR

    def test_pupil_is_white_in_dark_mode(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.PAUSED, dark_mode=True)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        offset_x = int(cx + pm.width() / dpr * 0.15 * dpr)
        assert _pixel_color(pm, offset_x, cy) == QColor("#FFFFFF")


class TestUnavailableIcon:
    """UNAVAILABLE state: almond outline with horizontal line, no pupil."""

    def test_no_pupil_circle_above_center(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.UNAVAILABLE)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        # Pixel above center: a pupil circle would be here, but a line wouldn't
        above_y = cy - int(pm.height() / dpr * 0.06 * dpr)
        assert _pixel_color(pm, cx, above_y) != PUPIL_COLOR

    def test_line_is_white_in_dark_mode(self, qtbot) -> None:
        icon = create_eye_icon(TrayIconState.UNAVAILABLE, dark_mode=True)
        pm = icon.pixmap(48)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        # Center pixel sits on the horizontal line
        assert _pixel_color(pm, cx, cy) == QColor("#FFFFFF")
