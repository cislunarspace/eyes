"""Tests for CalibrationView — the Qt countdown wrapper around CalibrationSession.

The calibration view owns the QTimer and the CalibrationSession; the
dialog composes it into its form. These tests exercise the view
without a QApplication event loop (the view's timer is driven
externally via qtbot.wait).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from eyes.calibration_view import CalibrationView


class TestCalibrationViewStart:
    def test_starts_session_and_emits_started(self, qtbot) -> None:
        view = CalibrationView()
        handler = MagicMock()
        view.calibration_started.connect(handler)
        view.start()
        assert view.is_calibrating
        handler.assert_called_once()


class TestCalibrationViewFeed:
    def test_feeds_samples_to_session(self) -> None:
        view = CalibrationView()
        view.start()
        view.feed(1.0, 2.0)
        view.feed(3.0, 4.0)
        assert view.session.sample_count == 2

    def test_feed_is_noop_when_inactive(self) -> None:
        view = CalibrationView()
        view.feed(1.0, 2.0)
        assert view.session.sample_count == 0


class TestCalibrationViewCompletion:
    def test_emits_completed_with_result(self, qtbot) -> None:
        view = CalibrationView(duration_seconds=0.3, tick_interval_ms=100)
        handler = MagicMock()
        view.calibration_completed.connect(handler)
        view.start()
        view.feed(5.0, 2.0)
        view.feed(6.0, 3.0)
        view.feed(7.0, 4.0)

        # Wait for the countdown to finish (0.3s + margin).
        qtbot.wait(450)

        assert not view.is_calibrating
        handler.assert_called_once()
        yaw, roll = handler.call_args[0]
        assert yaw is not None
        assert roll is not None

    def test_result_carries_sample_count(self, qtbot) -> None:
        view = CalibrationView(duration_seconds=0.2, tick_interval_ms=100)
        handler = MagicMock()
        view.calibration_completed.connect(handler)
        view.start()
        view.feed(1.0, 2.0)
        qtbot.wait(350)
        # Result is accessible via session.result().
        result = view.session.result()
        assert result is not None
        assert result.sample_count == 1

    def test_no_samples_emits_no_result(self, qtbot) -> None:
        view = CalibrationView(duration_seconds=0.2, tick_interval_ms=100)
        handler = MagicMock()
        view.calibration_completed.connect(handler)
        view.start()
        qtbot.wait(350)
        # No feed → session has no samples → no completed signal.
        handler.assert_not_called()


class TestCalibrationViewIsCalibrating:
    def test_true_while_countdown_active(self) -> None:
        view = CalibrationView()
        view.start()
        assert view.is_calibrating is True

    def test_false_before_start(self) -> None:
        view = CalibrationView()
        assert view.is_calibrating is False


class TestCalibrationViewCustomTickInterval:
    def test_respects_tick_interval_parameter(self, qtbot) -> None:
        view = CalibrationView(duration_seconds=0.3, tick_interval_ms=200)
        handler = MagicMock()
        view.calibration_completed.connect(handler)
        view.start()
        view.feed(1.0, 2.0)
        # With 200ms ticks, 0.3s duration → first tick at 200ms, session
        # finishes by ~400ms.
        qtbot.wait(500)
        assert not view.is_calibrating
        handler.assert_called_once()
