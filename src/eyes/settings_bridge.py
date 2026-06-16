"""SettingsBridge — single home for "config changed → rebuild everything".

Pulled out of AppController so the settings-rebuild sequence lives in
one place. Owns:
  - reloading the active config from the config store
  - rebuilding the classifier (neutral pose + thresholds) on the sense loop
  - rebuilding the accumulator (timing thresholds) on the sense loop
  - applying autostart
  - refreshing the language across window, overlay, tray
  - reloading after a calibration completes
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional, Protocol

from .autostart import AutostartManager
from .classifier import NeutralPose, Thresholds
from .config_store import ConfigStore
from .event_log import EventLog
from .i18n import set_language
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .sense_loop import AccumulatorConfig, SenseLoop
from .tray_controller import TrayController
from .types import AppConfig, AppEventKind


class SenseLoopLike(Protocol):
    """Minimal interface the bridge needs from the sense loop."""

    def update_classifier(
        self, neutral: NeutralPose, thresholds: Thresholds
    ) -> None: ...


class SenseLoopWithAccumulator(Protocol):
    """Sense-loop interface that also exposes the accumulator config knobs."""

    def update_classifier(
        self, neutral: NeutralPose, thresholds: Thresholds
    ) -> None: ...
    @property
    def engine(self) -> Any: ...


class WindowLike(Protocol):
    def refresh_language(self) -> None: ...


class OverlayLike(Protocol):
    def refresh_language(self) -> None: ...


class TrayLike(Protocol):
    def refresh_language(self) -> None: ...


class ConfigStoreLike(Protocol):
    def load(self) -> AppConfig: ...


class EventLogLike(Protocol):
    def append(self, kind: AppEventKind, **data: object) -> object: ...


class AutostartLike(Protocol):
    def apply_config(self, enabled: bool) -> None: ...


class SettingsBridge:
    """Applies a config to all the components that depend on it.

    The bridge does not own the components — it just knows which ones
    to poke when the config changes. The controller constructs it with
    references to the live components and calls `apply_config` from
    the settings-changed signal handler.
    """

    def __init__(
        self,
        config_store: ConfigStoreLike,
        sense_loop: SenseLoopWithAccumulator,
        autostart: AutostartLike,
        window: WindowLike,
        overlay: OverlayLike,
        tray: TrayLike,
    ) -> None:
        self._config_store = config_store
        self._sense_loop = sense_loop
        self._autostart = autostart
        self._window = window
        self._overlay = overlay
        self._tray = tray

    def apply_config(self) -> None:
        """Reload config and push it to all dependent components."""
        config = self._config_store.load()
        self._sense_loop.update_classifier(
            neutral=NeutralPose(yaw=config.neutral_yaw, roll=config.neutral_roll),
            thresholds=Thresholds(
                yaw_deg=config.yaw_threshold, roll_deg=config.roll_threshold
            ),
        )
        # Rebuild the accumulator's timing thresholds by mutating the
        # underlying engine. The engine exposes its setters via duck
        # typing; we set the four timing fields if present.
        engine = self._sense_loop.engine
        if hasattr(engine, "_off_axis_streak_threshold"):
            engine._off_axis_streak_threshold = (
                config.off_axis_streak_threshold_seconds
            )
        if hasattr(engine, "_off_axis_repeat_interval"):
            engine._off_axis_repeat_interval = (
                config.off_axis_repeat_interval_seconds
            )
        if hasattr(engine, "_facing_threshold"):
            engine._facing_threshold = config.facing_threshold_seconds
        if hasattr(engine, "_eyest_threshold"):
            engine._eyest_threshold = config.eyest_threshold_seconds

        self._autostart.apply_config(config.autostart_enabled)
        set_language(config.language)
        self._window.refresh_language()
        self._overlay.refresh_language()
        self._tray.refresh_language()

    def apply_calibration(self, yaw: float, roll: float) -> None:
        """After a calibration completes, reload config and rebuild the classifier.

        The accumulator's timing thresholds don't change on calibration —
        only the neutral pose reference does.
        """
        config = self._config_store.load()
        self._sense_loop.update_classifier(
            neutral=NeutralPose(yaw=config.neutral_yaw, roll=config.neutral_roll),
            thresholds=Thresholds(
                yaw_deg=config.yaw_threshold, roll_deg=config.roll_threshold
            ),
        )
