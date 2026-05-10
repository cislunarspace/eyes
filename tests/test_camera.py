"""Tests for CameraSource."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from eyes.camera import CameraSource


def _fake_frame() -> np.ndarray:
    return np.full((480, 640, 3), 128, dtype=np.uint8)


class TestCameraSource:
    def test_initial_state_not_available(self) -> None:
        cam = CameraSource(index=99)
        assert not cam.is_available

    def test_close_resets_available(self) -> None:
        cam = CameraSource(index=0)
        cam._available = True
        cam._cap = MagicMock()
        cam.close()
        assert not cam.is_available
        assert cam._cap is None

    @patch("cv2.VideoCapture")
    def test_open_returns_true_when_camera_available(self, mock_vc_class) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        assert cam.open() is True
        assert cam.is_available
        assert cam._cap is mock_cap

    @patch("cv2.VideoCapture")
    def test_open_returns_false_when_camera_unavailable(self, mock_vc_class) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        assert cam.open() is False
        assert not cam.is_available
        mock_cap.release.assert_called_once()

    def test_read_returns_none_when_not_available(self) -> None:
        cam = CameraSource(index=0)
        assert cam.read() is None

    @patch("cv2.VideoCapture")
    def test_read_returns_frame_when_available(self, mock_vc_class) -> None:
        frame = _fake_frame()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, frame)
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        cam.open()
        result = cam.read()
        assert result is not None
        np.testing.assert_array_equal(result, frame)

    @patch("cv2.VideoCapture")
    def test_read_marks_unavailable_on_false_frame(self, mock_vc_class) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (False, None)
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        cam.open()
        assert cam.is_available
        result = cam.read()
        assert result is None
        assert not cam.is_available

    @patch("cv2.VideoCapture")
    def test_retry_open_idempotent_when_available(self, mock_vc_class) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        cam.open()
        first_cap = cam._cap
        result = cam.retry_open()
        assert result is True
        assert cam._cap is first_cap  # not replaced
        mock_vc_class.assert_called_once()  # only called once (open, not again)

    @patch("cv2.VideoCapture")
    def test_retry_open_reopens_when_unavailable(self, mock_vc_class) -> None:
        mock_cap = MagicMock()
        mock_cap.isOpened.side_effect = [False, True]
        mock_vc_class.return_value = mock_cap

        cam = CameraSource(index=0)
        assert cam.open() is False
        assert cam.retry_open() is True
        assert cam.is_available
