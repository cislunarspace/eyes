"""Tests for SettingsBridge — the config-rebuild coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

from eyes.classifier import NeutralPose, Thresholds
from eyes.settings_bridge import SettingsBridge
from eyes.types import AppConfig


def _config(**overrides: object) -> AppConfig:
    base = dict(
        yaw_threshold=2.0,
        roll_threshold=90.0,
        neutral_yaw=0.0,
        neutral_roll=0.0,
        camera_index=0,
        snooze_until_iso=None,
        sound_enabled=False,
        autostart_enabled=False,
        language="zh-CN",
        off_axis_streak_threshold_seconds=0.3,
        off_axis_repeat_interval_seconds=10.0,
        facing_threshold_seconds=300.0,
        eyest_threshold_seconds=900.0,
    )
    base.update(overrides)
    return AppConfig(**base)  # type: ignore[arg-type]


class _FakeStore:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self.load_calls = 0

    def load(self) -> AppConfig:
        self.load_calls += 1
        return self._config


class _FakeSenseLoop:
    def __init__(self) -> None:
        self.update_calls: list[tuple[NeutralPose, Thresholds]] = []
        self.engine = _FakeEngine()

    def update_classifier(self, neutral: NeutralPose, thresholds: Thresholds) -> None:
        self.update_calls.append((neutral, thresholds))


class _FakeEngine:
    def __init__(self) -> None:
        self._off_axis_streak_threshold = 0.0
        self._off_axis_repeat_interval = 0.0
        self._facing_threshold = 0.0
        self._eyest_threshold = 0.0

    def reconfigure(
        self,
        *,
        off_axis_streak_threshold_seconds: float | None = None,
        off_axis_repeat_interval_seconds: float | None = None,
        facing_threshold_seconds: float | None = None,
        eyest_threshold_seconds: float | None = None,
    ) -> None:
        if off_axis_streak_threshold_seconds is not None:
            self._off_axis_streak_threshold = off_axis_streak_threshold_seconds
        if off_axis_repeat_interval_seconds is not None:
            self._off_axis_repeat_interval = off_axis_repeat_interval_seconds
        if facing_threshold_seconds is not None:
            self._facing_threshold = facing_threshold_seconds
        if eyest_threshold_seconds is not None:
            self._eyest_threshold = eyest_threshold_seconds


class TestApplyConfig:
    def test_calls_update_classifier(self) -> None:
        store = _FakeStore(_config(neutral_yaw=1.0, neutral_roll=2.0))
        sense_loop = _FakeSenseLoop()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=sense_loop,
            autostart=MagicMock(),
            window=MagicMock(),
            overlay=MagicMock(),
            tray=MagicMock(),
        )
        bridge.apply_config()
        assert len(sense_loop.update_calls) == 1
        neutral, thresholds = sense_loop.update_calls[0]
        assert neutral == NeutralPose(yaw=1.0, roll=2.0)
        assert thresholds.yaw_deg == 2.0

    def test_calls_autostart_apply_config(self) -> None:
        store = _FakeStore(_config(autostart_enabled=True))
        autostart = MagicMock()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=_FakeSenseLoop(),
            autostart=autostart,
            window=MagicMock(),
            overlay=MagicMock(),
            tray=MagicMock(),
        )
        bridge.apply_config()
        autostart.apply_config.assert_called_once_with(True)

    def test_refreshes_language_on_window_overlay_tray(self) -> None:
        store = _FakeStore(_config())
        window = MagicMock()
        overlay = MagicMock()
        tray = MagicMock()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=_FakeSenseLoop(),
            autostart=MagicMock(),
            window=window,
            overlay=overlay,
            tray=tray,
        )
        bridge.apply_config()
        window.refresh_language.assert_called_once()
        overlay.refresh_language.assert_called_once()
        tray.refresh_language.assert_called_once()

    def test_updates_accumulator_timing_thresholds(self) -> None:
        store = _FakeStore(
            _config(
                off_axis_streak_threshold_seconds=0.5,
                off_axis_repeat_interval_seconds=15.0,
                facing_threshold_seconds=250.0,
                eyest_threshold_seconds=850.0,
            )
        )
        sense_loop = _FakeSenseLoop()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=sense_loop,
            autostart=MagicMock(),
            window=MagicMock(),
            overlay=MagicMock(),
            tray=MagicMock(),
        )
        bridge.apply_config()
        engine = sense_loop.engine
        assert engine._off_axis_streak_threshold == 0.5
        assert engine._off_axis_repeat_interval == 15.0
        assert engine._facing_threshold == 250.0
        assert engine._eyest_threshold == 850.0


class TestApplyCalibration:
    def test_reloads_config_and_rebuilds_classifier(self) -> None:
        store = _FakeStore(_config(neutral_yaw=3.0, neutral_roll=-1.0))
        sense_loop = _FakeSenseLoop()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=sense_loop,
            autostart=MagicMock(),
            window=MagicMock(),
            overlay=MagicMock(),
            tray=MagicMock(),
        )
        bridge.apply_calibration(3.0, -1.0)
        assert len(sense_loop.update_calls) == 1
        neutral, _ = sense_loop.update_calls[0]
        assert neutral == NeutralPose(yaw=3.0, roll=-1.0)

    def test_does_not_change_accumulator_timing(self) -> None:
        store = _FakeStore(_config())
        sense_loop = _FakeSenseLoop()
        bridge = SettingsBridge(
            config_store=store,
            sense_loop=sense_loop,
            autostart=MagicMock(),
            window=MagicMock(),
            overlay=MagicMock(),
            tray=MagicMock(),
        )
        bridge.apply_calibration(0.0, 0.0)
        # Engine timing fields were not touched.
        engine = sense_loop.engine
        assert engine._off_axis_streak_threshold == 0.0
        assert engine._off_axis_repeat_interval == 0.0
