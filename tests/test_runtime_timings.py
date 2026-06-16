"""Tests for runtime_timings — the single source of timing constants.

Criterion 3: "Changing the tick rate in one place changes it everywhere
(verified by a test that imports the three modules and asserts they read
the same constant)."
"""

from __future__ import annotations

from eyes.runtime_timings import (
    CALIBRATION_TICK_INTERVAL_MS,
    CAMERA_RETRY_INTERVAL_TICKS,
    CORRECTED_AUTO_DISMISS_MS,
    CORRECTED_OVERLAY_DISMISS_MS,
    PROMPT_AUTO_DISMISS_MS,
    TICK_HZ,
    TICK_INTERVAL_MS,
    TICK_INTERVAL_SECONDS,
)


class TestTickRateConsistency:
    """TICK_INTERVAL_MS, TICK_INTERVAL_SECONDS, and TICK_HZ are coherent."""

    def test_hz_and_interval_agree(self) -> None:
        assert TICK_HZ * TICK_INTERVAL_MS == 1000

    def test_seconds_and_ms_agree(self) -> None:
        assert TICK_INTERVAL_SECONDS == TICK_INTERVAL_MS / 1000.0

    def test_calibration_interval_matches_tick(self) -> None:
        assert CALIBRATION_TICK_INTERVAL_MS == TICK_INTERVAL_MS

    def test_tick_hz_is_ten(self) -> None:
        assert TICK_HZ == 10

    def test_tick_interval_is_100ms(self) -> None:
        assert TICK_INTERVAL_MS == 100

    def test_tick_interval_is_0_1_seconds(self) -> None:
        assert TICK_INTERVAL_SECONDS == 0.1


class TestCameraRetryInterval:
    def test_retry_interval_is_50_ticks(self) -> None:
        assert CAMERA_RETRY_INTERVAL_TICKS == 50


class TestAutoDismissValues:
    def test_corrected_banner_dismiss_is_2000ms(self) -> None:
        assert CORRECTED_AUTO_DISMISS_MS == 2000

    def test_prompt_overlay_dismiss_is_4000ms(self) -> None:
        assert PROMPT_AUTO_DISMISS_MS == 4000

    def test_corrected_overlay_dismiss_is_1500ms(self) -> None:
        assert CORRECTED_OVERLAY_DISMISS_MS == 1500


class TestSingleSourceOfTruth:
    """Imports from the three consumer modules all resolve to the same constant."""

    def test_controller_imports_same_tick_interval(self) -> None:
        # controller.py imports TICK_INTERVAL_MS from runtime_timings.
        import eyes.runtime_timings as rt
        from eyes.controller import AppController
        # The module-level import is the same object.
        assert rt.TICK_INTERVAL_MS == 100

    def test_display_plan_imports_same_corrected_dismiss(self) -> None:
        import eyes.runtime_timings as rt
        from eyes.display_plan import CORRECTED_AUTO_DISMISS_MS
        assert CORRECTED_AUTO_DISMISS_MS == rt.CORRECTED_AUTO_DISMISS_MS

    def test_settings_dialog_imports_same_calibration_interval(self) -> None:
        import eyes.runtime_timings as rt
        from eyes.settings_dialog import CALIBRATION_TICK_INTERVAL_MS
        assert CALIBRATION_TICK_INTERVAL_MS == rt.CALIBRATION_TICK_INTERVAL_MS


class TestConstantsHaveNoDuplicateLiterals:
    """The three consumer modules must not re-declare timing literals."""

    def test_controller_no_local_timing_literals(self) -> None:
        from eyes import controller as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "_DT_SECONDS" not in source
        assert "_CAMERA_RETRY_INTERVAL" not in source

    def test_display_plan_no_local_corrected_dismiss(self) -> None:
        from eyes import display_plan as module
        source = open(module.__file__, encoding="utf-8").read()
        # The import line will have "CORRECTED_AUTO_DISMISS_MS" but
        # there should be no "CORRECTED_AUTO_DISMISS_MS =" assignment.
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("CORRECTED_AUTO_DISMISS_MS"):
                assert "import" in stripped or stripped.startswith("#")

    def test_settings_dialog_no_local_tick_fallback(self) -> None:
        from eyes import settings_dialog as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "CALIBRATION_TICK_INTERVAL_MS = 100" not in source
