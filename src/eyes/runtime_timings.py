"""Runtime timing constants — single source of truth.

All tick intervals, retry intervals, and auto-dismiss durations live
here so the main loop, the calibration timer, and the display-plan
auto-dismiss logic cannot drift out of sync.

Changing the tick rate here changes it everywhere: the main QTimer,
the MonitoringLoop's dt_seconds, the VisionInput's retry interval
(derived from the tick rate), and the calibration countdown timer.
"""

from __future__ import annotations

# --- Core tick rate ---

# 10 Hz tick — the cadence at which the monitoring loop reads a frame,
# runs the sense loop, and updates the UI.
TICK_HZ: int = 10

# Derived tick interval in milliseconds (100 ms for 10 Hz).
TICK_INTERVAL_MS: int = 1000 // TICK_HZ

# Derived tick interval in seconds (0.1 s for 10 Hz).
TICK_INTERVAL_SECONDS: float = TICK_INTERVAL_MS / 1000.0

# --- Camera retry ---

# How many ticks to wait before retrying the camera after a failure.
# At 10 Hz this is 50 ticks = 5 seconds.
CAMERA_RETRY_INTERVAL_TICKS: int = 50

# --- Calibration ---

# Calibration countdown tick interval, in milliseconds.
# Must match TICK_INTERVAL_MS so the calibration session and the main
# loop share the same sense of "one tick." A mismatch would cause the
# calibration countdown to run at a different cadence than the pose
# sampling that feeds it.
CALIBRATION_TICK_INTERVAL_MS: int = TICK_INTERVAL_MS

# --- Display auto-dismiss ---

# Duration (ms) the CORRECTED warning banner stays visible before
# auto-dismissing. The choice: long enough for the user to read the
# "good posture" message, short enough not to linger and become noise.
# Matches the 2-second corrected-remaining window in PostureTickEngine
# so the banner disappears at the same moment the engine transitions
# back to NORMAL.
CORRECTED_AUTO_DISMISS_MS: int = 2000

# Duration (ms) the good-posture and eye-rest notification overlays
# stay visible before auto-dismissing.
PROMPT_AUTO_DISMISS_MS: int = 4000

# Duration (ms) the corrected-notification overlay stays visible
# before auto-dismissing. Shorter than the banner because the overlay
# is a lighter confirmation, not a full-width warning.
CORRECTED_OVERLAY_DISMISS_MS: int = 1500
