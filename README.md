<div align="center">

# 👁️ Eyes

**Smart posture & eye-care companion for your desktop**

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![MediaPipe](https://img.shields.io/badge/Pose-MediaPipe-FF6F00?logo=google&logoColor=white)](https://ai.google.dev/edge/mediapipe)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/ouyangjiahong/eyes)

*A desktop application that uses your webcam to monitor head pose in real time — reminding you to sit straight and rest your eyes.*

[English](#features) · [中文文档](README_zh.md)

</div>

---

## Features

- **Real-time head pose detection** via webcam using MediaPipe FaceLandmarker
- **Yaw and roll tracking** - yaw (left/right head turn) and roll (head tilt) reported live
- **Pose state classification** - FACING_SCREEN, OFF_AXIS_LEFT, OFF_AXIS_RIGHT, OFF_AXIS_OTHER, NO_FACE
- **Neutral pose calibration** - hold a relaxed forward-facing pose for 5 seconds to set your personal baseline
- **Configurable thresholds** - adjust yaw and roll tolerance via Settings dialog
- **System tray** - runs in background; close the window to minimize to tray
- **Snooze** - pause reminders for 30 min, 1 hour, or indefinitely via tray menu
- **Periodic good-posture praise** - cumulative facing-time timer celebrates at 5 min
- **Eye rest reminders** - cumulative face-detected timer reminds at 15 min
- **Debounced corrective prompts** - first prompt after 5 s off-axis, then repeats every 30 s
- **Settings dialog** - GUI for thresholds, calibration, camera, sound, and autostart
- **Camera retry** - automatically retries every 5 s when camera is unavailable
- **Autostart** - optionally launch on OS login

## Requirements

| Requirement | Details |
| ----------- | ------- |
| **OS** | Windows, macOS, or Linux |
| **Python** | 3.12 or higher |
| **Camera** | Any webcam accessible via OpenCV (default index 0) |

---

## Quick Start

### Install with uv (recommended)

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
uv sync          # create venv & install dependencies
uv run python main.py
```

### Install with pip

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux / macOS
.venv\Scripts\activate     # Windows

pip install -e .
python main.py
```

### Specify a camera

```bash
python main.py        # default camera (index 0)
python main.py 1      # second camera
```

### Development install

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
uv sync --extra dev   # or: pip install -e ".[dev]"
uv run python main.py
```

---

## Usage

The application opens a window showing:

- **Live webcam preview** - your camera feed
- **Colored badge** - current pose state (green = facing screen, red = off-axis, amber = roll deviation, grey = no face)
- **Angle readout** - live yaw and roll in degrees (e.g. `yaw: -3.2°   roll: +1.1°`)

### System Tray

Closing the window minimizes the app to the system tray instead of quitting. The tray icon indicates the current state:

| Icon | State | Description |
| ---- | ----- | ----------- |
| 🟢 Green | Active | App is running and monitoring |
| 🟡 Yellow | Paused | Snooze is active |
| ⚪ Grey | Unavailable | Camera is unavailable |

**Tray menu options:**

- **Snooze 30 min** - Snooze for 30 minutes
- **Snooze 1 hour** - Snooze for 1 hour
- **Snooze indefinitely** - Snooze until manually resumed
- **Resume** - Resume monitoring (only enabled while snoozed)
- **Settings** - Open Settings dialog
- **Quit** - Quit the application completely

Snooze settings persist across app restarts.

### Neutral Pose Calibration

Hold a relaxed forward-facing pose for 5 seconds while the app is running. The app detects this stable forward-facing position and uses it as your personal baseline for all deviation checks. This makes the app work accurately regardless of how you naturally sit relative to the camera.

Alternatively, use the **Calibrate** button in the Settings dialog.

---

## Settings

Open Settings via the tray menu.

| Setting | Description |
| ------- | ----------- |
| Yaw threshold | Head turn tolerance, 5–30°. Beyond this → off-axis. |
| Roll threshold | Head tilt tolerance, 5–30°. Beyond this → roll deviation. |
| Neutral pose | Current calibrated baseline. Click **Calibrate** to recalibrate (hold forward-facing for 5 s). |
| Camera | Select which camera to use (0 = default webcam). |
| Sound | Toggle prompt sounds on/off. |
| Autostart | Toggle OS autostart on login. |

---

## Configuration

Settings are persisted to `~/.config/eyes/config.yaml` (via [platformdirs](https://pypi.org/project/platformdirs/)). You can edit this file directly or use the Settings dialog.

```yaml
yaw_threshold: 15.0        # Head turn tolerance in degrees
roll_threshold: 10.0       # Head tilt tolerance in degrees
neutral_yaw: 0.0           # Calibrated baseline yaw (set by calibration)
neutral_roll: 0.0          # Calibrated baseline roll (set by calibration)
camera_index: 0            # Webcam index to use
snooze_until_iso: null     # Snooze expiry (ISO 8601), null = not snoozed, "indefinite" = manual resume only
sound_enabled: false       # Enable/disable prompt sounds
autostart_enabled: false   # OS autostart on login
language: zh-CN            # UI language
```

---

## Architecture

### Project Structure

```text
eyes/
├── models/
│   └── face_landmarker.task    # MediaPipe face landmark model
├── src/eyes/
│   ├── __init__.py             # Package entry point, version
│   ├── camera.py               # CameraSource — webcam capture via OpenCV
│   ├── detector.py             # HeadPoseDetector — MediaPipe wrapper, returns (yaw, roll)
│   ├── classifier.py           # PoseClassifier + NeutralPose + Thresholds + classify()
│   ├── accumulator.py          # AccumulatorEngine — off-axis streak + S4/S5 timers
│   ├── overlay.py              # NotifierOverlay — always-on-top correction prompts
│   ├── config_store.py         # ConfigStore — atomic YAML config persistence
│   ├── settings_dialog.py      # SettingsDialog — GUI for thresholds, calibration, camera, sound, autostart
│   ├── tray_controller.py      # TrayController — system tray icon + snooze menu
│   ├── event_log.py            # EventLog — session event logging
│   ├── autostart.py            # AutostartManager — OS autostart integration
│   ├── calibration.py          # PoseSample + compute_median_pose()
│   ├── types.py                # AppConfig + AppEventKind
│   ├── main_window.py          # MainWindow — PySide6 GUI
│   └── controller.py           # AppController — 10 Hz tick loop
├── tests/                       # pytest tests
├── docs/
│   └── adr/                    # Architecture Decision Records
├── main.py                      # CLI entry point
└── pyproject.toml
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `camera.py` | Opens/retry/releases `cv2.VideoCapture`. Caller drives re-opening via `retry_open()`. |
| `detector.py` | Wraps MediaPipe `FaceLandmarker` in VIDEO mode. Returns `Optional[HeadPose]`. |
| `classifier.py` | Pure function `classify(pose, neutral, thresholds) → PoseState`. `pose=None` returns `NO_FACE`. |
| `accumulator.py` | Pure state machine: off-axis streak, S4 (facing time), S5 (presence time). Driven by external dt ticks. |
| `overlay.py` | Frameless always-on-top widget for correction prompts. Auto-dismisses after 4 seconds. |
| `config_store.py` | Atomic YAML read/write via temp-file-then-rename. |
| `settings_dialog.py` | PySide6 dialog with sliders, calibration button, camera selector, toggles. |
| `tray_controller.py` | `QSystemTrayIcon` with pause/resume/settings/quit menu. |
| `event_log.py` | Session event logger (state changes, prompts, camera events, snooze). |
| `autostart.py` | OS-specific autostart registration/removal. |
| `calibration.py` | `compute_median_pose()` — median of `PoseSample` list. |
| `types.py` | `AppConfig` (frozen dataclass), `AppEventKind` (enum). |
| `main_window.py` | `QMainWindow`. Owns `CameraSource` and `HeadPoseDetector`. Cleans up on close. |
| `controller.py` | Owns the 10 Hz `QTimer`. Calls camera read → detector → classifier → accumulator → window update each tick. |

### Data Flow

```text
Webcam frame (BGR, uint8)
  → CameraSource.read()
  → HeadPoseDetector.detect(frame)
    → MediaPipe FaceLandmarker (VIDEO mode)
    → 4×4 transformation matrix → 3×3 rotation block → euler angles
    → Optional[HeadPose(yaw, roll)]
  → PoseClassifier.classify(pose, neutral, thresholds)
    → compares against NeutralPose + Thresholds
    → PoseState (one of 5 states)
  → AccumulatorEngine.tick(state, dt)
    → tracks off-axis streak → fires correction if due
    → tracks S4/S5 accumulators → fires praise/eye-rest if due
  → MainWindow.set_state(yaw, roll, state)
    → updates readout label
    → updates badge color + text
  → MainWindow.update_frame(frame)
    → converts BGR → RGB → QImage → QPixmap
    → displays on video label
  → NotifierOverlay (if triggered by AccumulatorEngine)
    → shows always-on-top correction prompt
```

Loop runs at 10 Hz (100 ms per tick).

### State Machine

```text
┌─────────────────┐
│  NO_FACE        │ ← no face in frame
└────────┬────────┘
         │ face detected
         ▼
┌─────────────────────────────────┐
│  FACING_SCREEN                  │ ← |yaw_dev| ≤ yaw_threshold AND |roll_dev| ≤ roll_threshold
│  (neutral.yaw, neutral.roll)    │
└────────┬────────────────────────┘
         │ |yaw_dev| > yaw_threshold
         ▼
┌─────────────────────────────────┐
│  OFF_AXIS_LEFT  ← yaw_dev < 0   │ ← head turned to user's own left
│  OFF_AXIS_RIGHT ← yaw_dev > 0   │ ← head turned to user's own right
└─────────────────────────────────┘
         │
         │ |yaw_dev| ≤ yaw_threshold BUT |roll_dev| > roll_threshold
         ▼
┌─────────────────────────────────┐
│  OFF_AXIS_OTHER                 │ ← roll-only deviation (tilted onto shoulder)
└─────────────────────────────────┘
```

Note: OFF_AXIS_LEFT and OFF_AXIS_RIGHT take priority over OFF_AXIS_OTHER when both yaw and roll are out of threshold.

### Timers and Prompts

| Timer | Trigger | Reset | Behavior |
| ----- | ------- | ----- | -------- |
| **Off-Axis Streak** | OFF_AXIS_LEFT or OFF_AXIS_RIGHT | Returns to FACING_SCREEN or NO_FACE | First corrective prompt at 5 s. Repeats every 30 s while still off-axis. |
| **Facing Time (S4)** | FACING_SCREEN | Does NOT reset on brief deviation; only pauses | At 300 s cumulative facing time → praise prompt. Resets to 0 after firing. |
| **Presence Time (S5)** | Any face-detected state (not NO_FACE) | Does NOT reset on NO_FACE; only pauses | At 900 s cumulative presence → eye rest reminder. Resets to 0 after firing. |

**Snooze behavior:** When snooze is active, all timers and accumulators freeze at their current values (no progress, no regression). Resuming unblocks everything from where it left off.

### Design Decisions (ADRs)

See `docs/adr/` for full ADR documents:

- **ADR-0001** - Detect yaw and roll only; ignore pitch and eye gaze.
- **ADR-0002** - Cumulative time timers (wall-clock time not used).
- **ADR-0003** - MediaPipe for head pose.
- **ADR-0004** - Custom floating window over OS toast.

---

## Development

### Setup

```bash
# With uv (recommended)
uv sync --extra dev

# With pip
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
pytest --cov=src --cov-report=term-missing
```

### Code Quality

```bash
ruff check src/
```

---

## FAQ / Troubleshooting

### The app keeps running after closing the window

This is expected. Closing the window minimizes the app to the system tray. To fully quit, click **Quit** in the tray menu.

### Camera is in use by another application

The app retries every 5 seconds automatically. The tray icon turns grey while retrying. Close the conflicting app (Zoom, Teams, etc.) and the app will recover.

### Correction prompts keep appearing

You need to recalibrate your neutral pose. Face the screen in a relaxed posture for 5 seconds, or use **Settings → Calibrate**.

### Thresholds feel too strict / too loose

Open **Settings** from the tray menu and adjust the **Yaw threshold** and **Roll threshold** sliders.

### How does snooze work?

Click the tray icon, select **Snooze 30 min**, **Snooze 1 hour**, or **Snooze indefinitely**. During snooze the tray icon turns yellow and all timers freeze. Click **Resume** to end snooze early. Timed snoozes expire automatically.

### What is the good-posture praise?

After 300 s (5 min) of cumulative facing-screen time, you get an encouraging prompt. The timer pauses (not resets) when you look away.

### What is the eye-rest reminder?

After 900 s (15 min) of cumulative face-detected time, you get a "look into the distance" reminder. Leaving the camera pauses the timer without resetting it.

### No face detected

Make sure:

- Your face is clearly visible with adequate lighting
- The camera is aimed at your face, roughly at the same height
- You are within 2 meters of the camera

### Model download failed

MediaPipe downloads the face landmark model on first run. If it fails, the app retries on each subsequent run. The model URL is in `src/eyes/detector.py`.

## License

MIT License. See [LICENSE](LICENSE) for the full text.
