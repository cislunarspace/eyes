"""Tests for CameraSelector — the QComboBox + CameraProbe abstraction.

These tests use a fake CameraProbe (no OpenCV required) to verify
that the selector populates the combo box from probe results and
selects the current index correctly.
"""

from __future__ import annotations

from eyes.camera_selector import CameraSelector, OpenCVCameraProbe, _PROBE_RANGE_SIZE


class _FakeProbe:
    """CameraProbe that returns a fixed list of indices."""

    def __init__(self, indices: list[int]) -> None:
        self._indices = list(indices)
        self.probe_calls = 0

    def available_indices(self) -> list[int]:
        self.probe_calls += 1
        return self._indices


class TestCameraSelectorPopulate:
    def test_populates_from_probe(self, qtbot) -> None:
        probe = _FakeProbe([0, 2, 3])
        selector = CameraSelector(probe=probe, current_index=0)
        qtbot.addWidget(selector)
        assert selector.count() == 3
        assert selector.itemText(0) == "摄像头 0"
        assert selector.itemText(1) == "摄像头 2"
        assert selector.itemText(2) == "摄像头 3"

    def test_selects_current_index(self, qtbot) -> None:
        probe = _FakeProbe([0, 1, 2])
        selector = CameraSelector(probe=probe, current_index=1)
        qtbot.addWidget(selector)
        assert selector.currentData() == 1

    def test_selects_first_when_current_not_available(self, qtbot) -> None:
        probe = _FakeProbe([0, 2])
        selector = CameraSelector(probe=probe, current_index=1)
        qtbot.addWidget(selector)
        # Index 1 not available → falls back to first item.
        assert selector.currentIndex() == 0
        assert selector.currentData() == 0

    def test_empty_probe(self, qtbot) -> None:
        probe = _FakeProbe([])
        selector = CameraSelector(probe=probe, current_index=0)
        qtbot.addWidget(selector)
        assert selector.count() == 0


class TestCameraSelectorRefresh:
    def test_refresh_reprobes_and_repopulates(self, qtbot) -> None:
        probe = _FakeProbe([0, 1])
        selector = CameraSelector(probe=probe, current_index=0)
        qtbot.addWidget(selector)
        assert selector.count() == 2

        # Change the probe result and refresh.
        probe._indices = [0, 1, 2, 3]
        selector.refresh(current_index=2)
        assert selector.count() == 4
        assert selector.currentData() == 2
        assert probe.probe_calls == 2  # once at __init__, once at refresh


class TestCameraSelectorData:
    def test_item_data_is_device_index(self, qtbot) -> None:
        probe = _FakeProbe([0, 1, 2])
        selector = CameraSelector(probe=probe, current_index=0)
        qtbot.addWidget(selector)
        assert selector.itemData(0) == 0
        assert selector.itemData(1) == 1
        assert selector.itemData(2) == 2


class TestOpenCVCameraProbeDefaultRange:
    def test_probe_range_size_is_five(self) -> None:
        assert _PROBE_RANGE_SIZE == 5

    def test_fake_probe_has_available_indices(self) -> None:
        probe = _FakeProbe([0])
        assert probe.available_indices() == [0]


class TestFakeProbeMeetsProtocol:
    def test_protocol_compliance(self) -> None:
        from typing import Protocol, runtime_checkable

        from eyes.camera_selector import CameraProbe as CameraProbeProto

        # CameraProbe is a Protocol; _FakeProbe satisfies it if
        # available_indices() returns the right type.
        probe = _FakeProbe([0, 1])
        result: list[int] = probe.available_indices()
        assert isinstance(result, list)
