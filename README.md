# Eyes

A desktop application that uses your webcam to monitor head pose in real time and reminds you to adjust when you're not facing the screen, or to rest your eyes periodically.

## Features

- **Real-time head pose detection** via webcam using MediaPipe FaceLandmarker
- **Yaw and roll tracking** - yaw (left/right head turn) and roll (head tilt) reported live
- **Pose state classification** - FACE_SCREEN, OFF-AXIS LEFT, OFF-AXIS RIGHT, OFF-AXIS OTHER, NO FACE
- **Neutral pose calibration** - hold a relaxed forward-facing pose to set your personal baseline
- **Configurable thresholds** - adjust yaw and roll tolerance to suit your preference
- **Periodic good-posture praise** - cumulative facing-time timer celebrates when you stay on-axis
- **Debounced corrective prompts** - first prompt after 5 seconds off-axis, then repeats every 30 seconds
- **PySide6 GUI** - live webcam preview with colored pose badge and angle readout

## Requirements

- **OS**: Windows, macOS, or Linux
- **Python**: 3.12 or higher
- **Camera**: Any webcam accessible via OpenCV (default: camera index 0)
- **Dependencies**: MediaPipe, OpenCV, PySide6 (installed automatically)

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

## Usage

```bash
python -m eyes
python -m eyes 0          # explicit default camera
python -m eyes 1          # second camera
```

The application opens a window showing:

- **Live webcam preview** - your camera feed
- **Colored badge** - current pose state (green = facing screen, red = off-axis, amber = roll deviation, grey = no face)
- **Angle readout** - live yaw and roll in degrees (e.g. `yaw: -3.2 deg   roll: +1.1 deg`)

### Neutral Pose Calibration

Hold a relaxed forward-facing pose for 5 seconds while the app is running. The app detects this stable forward-facing position and uses it as your personal baseline for all deviation checks. This makes the app work accurately regardless of how you naturally sit relative to the camera.

## Configuration

### Default Thresholds

| Parameter    | Default   | Description                                                       |
| ------------ | --------- | ---------------------------------------------------------------- |
| `yaw_deg`    | 15 deg    | Head turn tolerance - beyond this, classified as off-axis          |
| `roll_deg`   | 10 deg    | Head tilt tolerance - beyond this, classified as roll deviation    |
| Neutral pose | (0 deg)  | Canonical "facing screen" baseline, adjustable via calibration     |

### Changing Thresholds

Thresholds are currently configured by editing `src/eyes/classifier.py`:

```python
@dataclass(frozen=True)
class Thresholds:
    yaw_deg: float = 15.0   # adjust this
    roll_deg: float = 10.0  # adjust this
```

A configuration file interface is planned for a future release.

## Architecture

### Project Structure

```text
eyes/
├── models/
│   └── face_landmarker.task    # MediaPipe face landmark model
├── src/eyes/
│   ├── __init__.py             # Package entry point, version
│   ├── camera.py               # CameraSource - webcam capture via OpenCV
│   ├── detector.py             # HeadPoseDetector - MediaPipe wrapper, returns (yaw, roll)
│   ├── classifier.py           # PoseClassifier - pure function: (yaw, roll) → PoseState
│   ├── main_window.py         # MainWindow - PySide6 GUI with preview, readout, badge
│   └── controller.py          # AppController - 10 Hz tick loop: read → detect → classify → update
├── tests/
│   ├── conftest.py             # Pytest fixtures and MediaPipe test-image helpers
│   ├── test_camera.py          # CameraSource tests
│   ├── test_detector.py        # HeadPoseDetector tests + rotation matrix Euler tests
│   └── test_classifier.py      # PoseClassifier unit and parametric tests
├── docs/
│   └── adr/                    # Architecture Decision Records
├── main.py                     # CLI entry point: parses [camera_index], launches AppController
└── pyproject.toml
```

### Module Responsibilities

| Module            | Responsibility                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------- |
| `camera.py`       | Opens/retry/releases `cv2.VideoCapture`. Caller drives re-opening via `retry_open()`.           |
| `detector.py`     | Wraps MediaPipe `FaceLandmarker` in VIDEO mode. Returns `Optional[(yaw_deg, roll_deg)]`.        |
| `classifier.py`   | Pure function `classify(yaw, roll, neutral, thresholds) → PoseState`. Stateless, no side effects. |
| `main_window.py`  | PySide6 `QMainWindow`. Owns `CameraSource` and `HeadPoseDetector`. Cleans up on close.          |
| `controller.py`   | Owns the 10 Hz `QTimer`. Calls camera read → detector → classifier → window update each tick.  |

### Data Flow

```text
Webcam frame (BGR, uint8)
  → CameraSource.read()
  → HeadPoseDetector.detect(frame)
    → MediaPipe FaceLandmarker (Video mode)
    → 4×4 transformation matrix → 3×3 rotation block
    → atan2(R[1,0], R[0,0]) → yaw_deg
    → atan2(R[2,1], R[2,2]) → roll_deg
    → Optional[(yaw_deg, roll_deg)]
  → PoseClassifier.classify(yaw, roll)
    → compares against NeutralPose + Thresholds
    → PoseState (one of 5 states)
  → MainWindow.set_state(yaw, roll, state)
    → updates readout label
    → updates badge color + text
  → MainWindow.update_frame(frame)
    → converts BGR → RGB → QImage → QPixmap
    → displays on video label
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
│  FACING_SCREEN                   │ ← |yaw_dev| ≤ yaw_threshold AND |roll_dev| ≤ roll_threshold
│  (neutral.yaw=0, neutral.roll=0) │
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

| Timer                      | Trigger                                 | Reset                                   | Behavior                                                                                     |
| -------------------------- | --------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------ |
| **Facing Time Accumulator** | In `FACING_SCREEN` state                | Resets at 300s when prompt fires        | At 300s cumulative facing time → "良好" (good posture) praise. Pauses when not facing screen. |
| **Off-Axis Streak**        | In `OFF_AXIS_LEFT` or `OFF_AXIS_RIGHT`  | Resets on return to `FACING_SCREEN`/`NO_FACE` | First corrective prompt at 5s. Repeats every 30s while still off-axis.                     |

### Design Decisions (ADRs)

- **ADR-0001** - Detect yaw and roll only; ignore pitch and eye gaze. Rationale: pitch alarms misfire on legitimate looking-down; gaze tracking is out of scope for v1.
- **ADR-0002** - Cumulative time timers (wall-clock time not used). Rationale: the spec's "每 5 分钟" is cumulative session time, not a wall-clock interval.
- **ADR-0003** - MediaPipe for head pose. Rationale: well-tested, pre-trained, runs on CPU, good balance of accuracy and latency.
- **ADR-0004** - Custom floating window over OS toast. Rationale: OS-native notifications are too intrusive for frequent reminders; a custom overlay gives control over appearance and debounce.

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

## FAQ / Troubleshooting

### Camera not detected

The app prints a message to the readout label if the camera fails to open. Try:

- Unplugging and replugging the webcam
- Trying a different camera index: `python -m eyes 1`
- Closing other applications that may be using the camera (Zoom, Teams, etc.)

### No face detected

- Make sure your face is visible and well-lit
- Ensure the camera is pointed at you at approximately face level
- The MediaPipe model works best within ~2 meters of the camera

### Model download fails

On first run, MediaPipe downloads the face landmarker model automatically. If the download fails, the app falls back to downloading from GCS on each run. If you need a manual download, the model URL is documented in `src/eyes/detector.py`.

### "请向右调整" / "请向左调整" keeps firing

You may need to recalibrate your neutral pose. Hold a relaxed forward-facing position for 5 seconds. If you naturally sit at an angle, recalibrating will set a more accurate baseline.

### Thresholds feel too strict / too loose

Edit `src/eyes/classifier.py` and adjust `Thresholds.yaw_deg` and `Thresholds.roll_deg`. A future release will expose this via a config file or GUI slider.

## License

MIT License. See [LICENSE](LICENSE) for the full text.
