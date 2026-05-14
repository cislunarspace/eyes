# Eyes

A desktop application that uses your webcam to monitor head pose in real time and reminds you to adjust when you're not facing the screen, or to rest your eyes periodically.

---

## Features

- **Real-time head pose detection** via webcam using MediaPipe FaceLandmarker
- **Yaw and roll tracking** - yaw (left/right head turn) and roll (head tilt) reported live
- **Pose state classification** - FACE_SCREEN, OFF-AXIS LEFT, OFF-AXIS RIGHT, OFF-AXIS OTHER, NO FACE
- **Neutral pose calibration** - hold a relaxed forward-facing pose for 5 seconds to set your personal baseline
- **Configurable thresholds** - adjust yaw and roll tolerance via Settings dialog
- **System tray** - runs in background; close the window to minimize to tray
- **Snooze** - pause reminders for 30 minutes, 1 hour, or indefinitely via tray menu
- **Periodic good-posture praise** - cumulative facing-time timer celebrates at 300s (5 min)
- **Eye rest reminders** - cumulative face-detected timer reminds at 900s (15 min)
- **Debounced corrective prompts** - first prompt after 5 seconds off-axis, then repeats every 30 seconds
- **Settings dialog** - GUI for thresholds, calibration, camera selection, sound, and autostart
- **Persistent configuration** - settings saved to `~/.config/eyes/config.yaml`
- **Camera retry** - automatically retries every 5 seconds when camera is unavailable
- **Autostart** - optionally launch on OS login
- **PySide6 GUI** - live webcam preview with colored pose badge and angle readout

## Requirements

- **OS**: Windows, macOS, or Linux
- **Python**: 3.12 or higher
- **Camera**: Any webcam accessible via OpenCV (default: camera index 0)
- **Dependencies**: MediaPipe, OpenCV, PySide6 (installed automatically)

---

## Installation

### Install from PyPI

```bash
pip install eyes
```

The MediaPipe model is downloaded automatically on first use.

### Install from source

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
pip install .
```

### Development install

```bash
git clone https://github.com/ouyangjiahong/eyes.git
cd eyes
pip install -e ".[dev]"
```

---

## Usage

```bash
python -m eyes
python -m eyes 0          # explicit default camera
python -m eyes 1          # second camera
```

The application opens a window showing:

- **Live webcam preview** - your camera feed
- **Colored badge** - current pose state (green = facing screen, red = off-axis, amber = roll deviation, grey = no face)
- **Angle readout** - live yaw and roll in degrees (e.g. `yaw: -3.2°   roll: +1.1°`)

### System Tray

Closing the window minimizes the app to the system tray instead of quitting. The tray icon indicates the current state:

| Icon | State | Description |
| ---- | ----- | ----------- |
| Green | 活跃 (Active) | App is running and monitoring |
| Yellow | 已暂停 (Paused) | Snooze is active |
| Grey | 不可用 (Unavailable) | Camera is unavailable |

**Tray menu options:**

- **暂停 30 分钟** - Snooze for 30 minutes
- **暂停 1 小时** - Snooze for 1 hour
- **暂停直到我恢复** - Snooze indefinitely until manually resumed
- **恢复** - Resume monitoring (only enabled while snoozed)
- **打开设置** - Open Settings dialog
- **退出** - Quit the application completely

Snooze settings persist across app restarts.

### Neutral Pose Calibration

Hold a relaxed forward-facing pose for 5 seconds while the app is running. The app detects this stable forward-facing position and uses it as your personal baseline for all deviation checks. This makes the app work accurately regardless of how you naturally sit relative to the camera.

Alternatively, use the **校准中立姿态** button in the Settings dialog.

---

## Settings

Open Settings via **打开设置** in the tray menu.

| Setting | Description |
| ------- | ----------- |
| 偏航阈值 | Head turn tolerance (yaw), 5-30°. Beyond this threshold, classified as off-axis. |
| 翻滚阈值 | Head tilt tolerance (roll), 5-30°. Beyond this threshold, classified as roll deviation. |
| 中立姿态 | Current calibrated baseline pose. Click **校准中立姿态** to recalibrate (hold forward-facing for 5 seconds). |
| 摄像头 | Select which camera to use (0 = default webcam). |
| 提示音 | Toggle prompt sounds on/off. |
| 开机自启 | Toggle OS autostart on login. |

---

## Configuration

Settings are persisted to `~/.config/eyes/config.yaml` (via [platformdirs](https://pypi.org/project/platformdirs/)). You can edit this file directly or use the Settings dialog.

### Config Schema

```yaml
yaw_threshold: 15.0        # Head turn tolerance in degrees
roll_threshold: 10.0       # Head tilt tolerance in degrees
neutral_yaw: 0.0           # Calibrated baseline yaw (set by calibration)
neutral_roll: 0.0          # Calibrated baseline roll (set by calibration)
camera_index: 0            # Webcam index to use
snooze_until_iso: null     # Snooze expiry timestamp (ISO 8601), null = not snoozed, "indefinite" = manual resume only
sound_enabled: false       # Enable/disable prompt sounds
autostart_enabled: false   # OS autostart on login
language: zh-CN            # UI language (currently Chinese-only)
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
| **Off-Axis Streak** | OFF_AXIS_LEFT or OFF_AXIS_RIGHT | Returns to FACING_SCREEN or NO_FACE | First corrective prompt at 5s. Repeats every 30s while still off-axis. |
| **Facing Time Accumulator (S4)** | FACING_SCREEN | Does NOT reset on brief deviation; only pauses | At 300s cumulative facing time → praise prompt. Resets to 0 after firing. |
| **Presence Time Accumulator (S5)** | Any face-detected state (not NO_FACE) | Does NOT reset on NO_FACE; only pauses | At 900s cumulative presence → eye rest reminder. Resets to 0 after firing. |

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
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install with dev dependencies
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

### Pre-commit

Not yet configured. See `AGENTS.md` for project conventions.

---

## FAQ / Troubleshooting

### 关闭窗口后应用仍在运行

这是正常行为。关闭窗口会将应用最小化到系统托盘。关闭摄像头后会在托盘图标上显示"摄像头被其他程序占用…等待恢复"。如需完全退出，请点击托盘菜单中的 **退出**。

### 摄像头被其他程序占用

应用会每 5 秒自动重试一次。重试期间托盘图标显示为灰色，窗口中会显示"摄像头被其他程序占用…等待恢复"。关闭占用摄像头的应用（如 Zoom、Teams 等），应用会自动恢复。

### "请向右调整" / "请向左调整" 不断弹出

你需要重新校准中立姿态。面向屏幕保持放松的坐姿 5 秒，或在 **打开设置** → **校准中立姿态** 中重新校准。如果自然坐姿有角度偏差，重新校准会设置更准确的中立基准。

### 阈值感觉太严格 / 太宽松

在托盘菜单中点击 **打开设置**，使用滑块调整 **偏航阈值** 和 **翻滚阈值**。

### 如何使用暂停功能？

点击托盘图标打开菜单，选择 **暂停 30 分钟**、**暂停 1 小时** 或 **暂停直到我恢复**。暂停期间托盘图标显示为黄色，所有提醒和计时器冻结。点击 **恢复** 可手动解除暂停。定时暂停会在到期后自动解除。

### 良好姿势提醒是做什么的？

累计面向屏幕时间达到 300 秒（5 分钟）时，会显示鼓励提示。这不是实时计时，而是在你保持正确姿势时逐渐累加的。

### 眺望远方提醒是做什么的？

累计检测到人脸时间达到 900 秒（15 分钟）时，会显示"请眺望远方"提示，提示你让眼睛休息一下。离开摄像头时计时暂停，但不会重置。

### 没有检测到人脸

请确保：

- 面部清晰可见且光照充足
- 摄像头对准你的面部，大致在同一高度
- 距离摄像头在 2 米以内

### 模型下载失败

首次运行时，MediaPipe 会自动下载人脸特征点模型。如果下载失败，应用会回退到每次运行时从 GCS 下载。如果需要手动下载，模型 URL 记录在 `src/eyes/detector.py` 中。

## License

MIT License. See [LICENSE](LICENSE) for the full text.
