"""Tests for VisionInput — encapsulates camera + detector lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from eyes.vision_input import FrameReady, VisionInput, VisionUnavailable


def _fake_frame() -> np.ndarray:
    return np.full((480, 640, 3), 128, dtype=np.uint8)


class TestStart:
    def test_start_returns_none_when_camera_opens_and_detector_builds(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        detector = object()
        factory = MagicMock(return_value=detector)

        vision = VisionInput(camera=camera, detector_factory=factory)
        result = vision.start()

        assert result is None
        assert vision.detector is detector
        assert vision.is_available is True

    def test_start_returns_unavailable_when_camera_fails_to_open(self) -> None:
        camera = MagicMock()
        camera.open.return_value = False
        factory = MagicMock()

        vision = VisionInput(camera=camera, detector_factory=factory)
        result = vision.start()

        assert isinstance(result, VisionUnavailable)
        assert result.just_failed is True
        assert result.detector_error is None
        assert vision.is_available is False
        factory.assert_not_called()

    def test_start_returns_detector_error_and_closes_camera_when_detector_fails(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        factory = MagicMock(side_effect=RuntimeError("boom"))

        vision = VisionInput(camera=camera, detector_factory=factory)
        result = vision.start()

        assert isinstance(result, VisionUnavailable)
        assert result.just_failed is True
        assert result.detector_error == "MODEL_LOAD_FAILED: boom"
        camera.close.assert_called_once()
        assert vision.is_available is False
        assert vision.detector is None


class TestTick:
    def test_tick_returns_frame_ready_when_camera_available(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        camera.is_available = True
        camera.read.side_effect = [_fake_frame(), _fake_frame()]
        factory = MagicMock(return_value=object())

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.start()

        result = vision.tick()
        assert isinstance(result, FrameReady)
        assert result.just_resumed is False
        np.testing.assert_array_equal(result.frame, _fake_frame())

    def test_tick_signals_just_failed_once_when_camera_drops(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        camera.is_available = True
        camera.read.return_value = _fake_frame()
        factory = MagicMock(return_value=object())

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.start()

        camera.is_available = False

        first = vision.tick()
        second = vision.tick()
        third = vision.tick()

        assert isinstance(first, VisionUnavailable) and first.just_failed is True
        assert isinstance(second, VisionUnavailable) and second.just_failed is False
        assert isinstance(third, VisionUnavailable) and third.just_failed is False

    def test_tick_throttles_retry_when_unavailable(self) -> None:
        """When unavailable, retry_open is called only once per retry interval."""
        camera = MagicMock()
        camera.open.return_value = False
        camera.is_available = False
        camera.retry_open.return_value = False
        factory = MagicMock(return_value=object())

        # retry every 3 ticks
        vision = VisionInput(camera=camera, detector_factory=factory, retry_interval_ticks=3)
        vision.start()  # initial fail; counts as a retry attempt? No — start() opens directly.
        camera.retry_open.reset_mock()

        # Tick 1, 2: skipped (still in throttle window). Tick 3: retry.
        vision.tick()
        vision.tick()
        assert camera.retry_open.call_count == 0
        vision.tick()
        assert camera.retry_open.call_count == 1
        vision.tick()
        vision.tick()
        assert camera.retry_open.call_count == 1
        vision.tick()
        assert camera.retry_open.call_count == 2

    def test_tick_signals_just_resumed_once_on_recovery(self) -> None:
        camera = MagicMock()
        camera.open.return_value = False  # initial start fails
        camera.is_available = False
        camera.retry_open.return_value = True
        factory = MagicMock(return_value=object())

        vision = VisionInput(camera=camera, detector_factory=factory, retry_interval_ticks=1)
        vision.start()  # unavailable

        # On retry, retry_open succeeds → camera flips available; subsequent read returns frame
        def _flip_available() -> bool:
            camera.is_available = True
            return True
        camera.retry_open.side_effect = _flip_available
        camera.read.return_value = _fake_frame()

        first = vision.tick()
        second = vision.tick()

        assert isinstance(first, FrameReady)
        assert first.just_resumed is True
        assert isinstance(second, FrameReady)
        assert second.just_resumed is False

    def test_tick_builds_detector_on_recovery_when_initial_load_failed(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        camera.is_available = True
        factory = MagicMock(side_effect=[RuntimeError("boom"), object()])

        vision = VisionInput(camera=camera, detector_factory=factory, retry_interval_ticks=1)
        result = vision.start()
        assert isinstance(result, VisionUnavailable)
        assert result.detector_error == "MODEL_LOAD_FAILED: boom"
        assert vision.detector is None

        # Camera was closed; on retry, reopen succeeds and detector builds.
        camera.is_available = False
        def _flip_available() -> bool:
            camera.is_available = True
            return True
        camera.retry_open.side_effect = _flip_available
        camera.read.return_value = _fake_frame()

        result = vision.tick()
        assert isinstance(result, FrameReady)
        assert result.just_resumed is True
        assert vision.detector is not None

    def test_tick_returns_detector_error_when_retry_succeeds_but_detector_fails(self) -> None:
        camera = MagicMock()
        camera.open.return_value = False
        camera.is_available = False
        factory = MagicMock(side_effect=RuntimeError("boom"))

        vision = VisionInput(camera=camera, detector_factory=factory, retry_interval_ticks=1)
        vision.start()  # camera failed; factory not called

        def _flip_available() -> bool:
            camera.is_available = True
            return True
        camera.retry_open.side_effect = _flip_available

        result = vision.tick()
        assert isinstance(result, VisionUnavailable)
        assert result.detector_error == "MODEL_LOAD_FAILED: boom"
        camera.close.assert_called()


class TestLifecycle:
    def test_set_camera_index_delegates_to_camera(self) -> None:
        camera = MagicMock()
        camera.index = 0
        factory = MagicMock(return_value=object())

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.set_camera_index(2)

        camera.set_index.assert_called_once_with(2)

    def test_set_camera_index_is_noop_when_index_unchanged(self) -> None:
        camera = MagicMock()
        camera.index = 1
        factory = MagicMock(return_value=object())

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.set_camera_index(1)

        camera.set_index.assert_not_called()

    def test_close_releases_camera_and_detector(self) -> None:
        camera = MagicMock()
        camera.open.return_value = True
        camera.is_available = True
        camera.read.return_value = _fake_frame()
        detector = MagicMock()
        factory = MagicMock(return_value=detector)

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.start()

        vision.close()

        camera.close.assert_called_once()
        detector.close.assert_called_once()

    def test_close_handles_no_detector(self) -> None:
        camera = MagicMock()
        factory = MagicMock()

        vision = VisionInput(camera=camera, detector_factory=factory)
        vision.close()

        camera.close.assert_called_once()  # idempotent
