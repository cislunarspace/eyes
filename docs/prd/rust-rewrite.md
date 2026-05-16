# PRD — Full Rust/Tauri rewrite of Eyes

## Problem Statement

I am the maintainer and only user of Eyes. Today the app is a Python 3.12 + PySide6 + MediaPipe desktop application that watches my webcam, classifies my head pose, and prompts me to sit straight or rest my eyes. It works, but I want to migrate the entire stack to Rust as a vibe-coding learning exercise: I want to keep the same product behavior while replacing Python/PySide/MediaPipe with a Rust + Tauri application I can keep evolving. I do not want a gradual core extraction with PyO3 bindings — I want the Python implementation gone by the end of the migration.

The current implementation also pins me to MediaPipe FaceLandmarker, a heavy Python install, and a PyInstaller-based bundling story that is awkward on Windows. The rewrite is the opportunity to land on `ort` (ONNX Runtime), OpenCV via Rust, and a Tauri installer.

## Solution

A full Rust rewrite of Eyes shipped as a Tauri 2 desktop application with a thin React + TypeScript + Vite frontend. The Rust backend owns the camera, the detector, the posture state machine, the configuration, and the system integration (tray, autostart, single instance). The web frontend handles the main window, the always-on-top reminder window, and the settings page, talking to the backend via Tauri commands and events.

Functional equivalence with the existing app is the contract:

- The same head-pose-driven correction, "good posture" praise, and eye-rest reminders fire at the same configured intervals.
- The same warning-level state machine (NORMAL → WARNING → SEVERE → CORRECTED → NORMAL) drives the in-window banner.
- The same calibration flow (5-second median pose) and the same snooze persistence semantics (`null` / `"indefinite"` / future ISO with malformed/expired handling) work across restarts.
- The existing YAML configuration file is read/written compatibly so my current settings survive the cutover.

The ONNX detector replaces MediaPipe. The default head-pose path is 2D landmarks plus OpenCV `solvePnP`. Detection parity is **behavioral**: pose classifications and reminders match the Python version after calibration, but raw yaw/roll values are not required to match MediaPipe.

The migration is executed as eight runnable milestones (M1 Tauri skeleton → M8 legacy cleanup). Python source, tests, and CI stay in the repository unchanged until M7 acceptance, then are removed in M8.

The first-stage required platform is Windows. macOS and Linux are deferred until Windows is fully validated.

## User Stories

1. As the maintainer, I want a Tauri 2 application skeleton with a React + TypeScript + Vite frontend, so that I can vibe-code the rest of the rewrite on a familiar shell.
2. As the user, I want the main window to open when I launch the app, so that I can see that Eyes is running.
3. As the user, I want a system tray icon to be visible whenever the app is running, so that I always know its status.
4. As the user, I want closing the main window to hide it instead of quitting, so that monitoring continues silently in the background.
5. As the user, I want the tray menu to offer Show, Settings, and Quit, so that I can return to the app or end the session intentionally.
6. As the user, I want only `Quit` to actually end the process, so that I don't accidentally kill background monitoring.
7. As the user, I want a single instance of Eyes at most, so that autostart plus a manual launch don't end up fighting over the camera.
8. As the user, I want a second launch attempt to focus the existing window, so that "double-clicking the icon" feels like the OS expects.
9. As the maintainer, I want the Rust backend to read and write the existing YAML config at the existing platform path, so that my configured thresholds, calibration, snooze state, language, and autostart preference survive the migration.
10. As the maintainer, I want config writes to be atomic (temp file then rename), so that a crash mid-write cannot corrupt my settings.
11. As the maintainer, I want missing config fields to be filled in with defaults, so that older or partially-written files still load.
12. As the user, I want the same head-pose classifier semantics (FACING_SCREEN, OFF_AXIS_LEFT, OFF_AXIS_RIGHT, OFF_AXIS_OTHER, NO_FACE) as today, so that the rewrite feels like the same product.
13. As the user, I want the same posture tick engine semantics — off-axis streak with repeat interval, facing-time praise, presence-time eye-rest reminder, and the warning-level state machine — so that prompt timing is unchanged.
14. As the user, I want the same calibration flow (5 seconds, median yaw and roll), so that recalibration produces the same baseline I'm used to.
15. As the user, I want reminders to be silenced while calibration is running, so that the calibration prompt isn't drowned out by other prompts.
16. As the user, I want a no-face-the-whole-time calibration to fail without changing my saved neutral pose, so that a bad calibration can't ruin my baseline.
17. As the user, I want to be able to cancel an in-progress calibration, so that I can abort if I get interrupted.
18. As the user, I want the same snooze options as today — 30 minutes, 1 hour, indefinite, plus Resume — driven from the tray menu, so that pausing reminders feels identical.
19. As the user, I want snooze state to persist across restarts the same way Python did (`null`, `"indefinite"`, future ISO, with malformed/expired handled), so that quitting and reopening doesn't lose or mis-restore my pause.
20. As the user, I want detection to keep running while I'm snoozed, but reminders to stay silent, so that resume picks up immediately.
21. As the maintainer, I want a Rust monitoring worker that owns the camera, detector, and posture engine, so that the Tauri command handlers stay thin and the worker is testable in isolation.
22. As the maintainer, I want the worker driven by external `Tick` commands at 10 Hz, so that tests can drive deterministic time without a real clock.
23. As the user, I want the main window to show a live yaw/roll readout with the current pose state badge, so that I can see what the detector is reporting.
24. As the user, I want the main window to show a low-FPS camera preview, so that I can confirm the camera is working and I'm framed correctly.
25. As the user, I want the camera unavailable state to show a clear banner in the main window, so that I notice when monitoring isn't actually running.
26. As the user, I want the camera to retry every 5 seconds when unavailable, so that recovery is automatic when I plug the webcam back in.
27. As the user, I want a missing or busy camera at startup not to crash the app, so that I can still open settings and adjust camera index.
28. As the user, I want the same in-window warning banner behavior (NORMAL → WARNING → SEVERE → CORRECTED → NORMAL) as today, so that visual escalation feels familiar.
29. As the user, I want correction prompts (left / right), good-posture praise, eye-rest, and "corrected" acknowledgement to appear in an always-on-top reminder window that auto-dismisses, so that I get the same overlay experience as today (consistent with ADR 0004).
30. As the user, I want reminders to fire even when the main window is hidden to the tray, so that the product still does its job in the background.
31. As the maintainer, I want the head-pose detector to use an ONNX face detector + landmark/head-pose model loaded via `ort`, so that we are not coupled to MediaPipe's Python wheel anymore.
32. As the maintainer, I want a `Detector` trait so the ONNX implementation can be swapped or faked, so that integration tests don't have to load real models.
33. As the maintainer, I want the default head-pose path to be 2D landmarks + OpenCV `solvePnP`, so that we are not dependent on a model providing 3D landmark depth.
34. As the maintainer, I want the chosen ONNX model's license, source, file size, and CPU inference latency captured in an ADR, so that future maintenance has the rationale.
35. As the maintainer, I want the model spike to be time-boxed to two working days with a fallback (OpenCV YuNet + simpler geometry), so that detector selection cannot silently consume the migration.
36. As the user, I want yaw sign convention preserved (positive = head turned to my own right), so that the calibration baseline still corresponds to "looking forward."
37. As the maintainer, I want behavioral parity instead of numeric parity for yaw/roll, so that any reasonable ONNX model can be used as long as classification and prompt outcomes match.
38. As the user, I want a Settings page exposing yaw threshold, roll threshold, camera index, language, sound enabled, and autostart enabled, so that I can configure Eyes from the UI without editing YAML.
39. As the user, I want advanced timing fields (off-axis streak threshold, off-axis repeat interval, facing-time threshold, eye-rest threshold) to round-trip through the YAML even if they aren't shown in the UI, so that power users can still tune timing.
40. As the user, I want saving settings to apply immediately to the running worker, so that I can iterate on thresholds without restarting.
41. As the user, I want changing the camera index from settings to reopen the camera with the retry path, so that I can switch webcams without losing the unavailable banner behavior.
42. As the user, I want the main window, reminder window, and tray menu text to all refresh when I switch language, so that the app is consistently localized.
43. As the user, I want at least Simplified Chinese and US English supported in the UI, so that I can use the language I'm used to.
44. As the user, I want a Calibrate button on the Settings page that runs the worker-side 5-second session, so that I can recalibrate without a separate flow.
45. As the user, I want the calibration UI to show remaining seconds and sample count, so that I know progress and that samples are landing.
46. As the user, I want completed calibration to write `neutral_yaw` and `neutral_roll` into the YAML and to take effect immediately in the running classifier, so that I don't need to restart.
47. As the user, I want the Windows autostart toggle to actually register/unregister an autostart entry at user level, so that Eyes really does start with my session.
48. As the maintainer, I want autostart implemented via `tauri-plugin-autostart`, so that I'm not maintaining registry/shortcut code by hand.
49. As the user, I want `sound_enabled` to be persisted as a setting and shown in the UI, so that the toggle round-trips even if real audio playback is added later.
50. As the maintainer, I want all backend events to flow through a small, stable schema (status-updated, preview-frame, prompt-fired, camera-state-changed, calibration-updated, config-updated, snooze-updated), so that the frontend can be coded against a fixed contract.
51. As the maintainer, I want preview frames on their own event channel, so that high-frequency JPEG payloads don't bloat the status feed.
52. As the maintainer, I want a JSONL event log written to the platform data directory covering STATE_CHANGE, PROMPT_FIRED, CAMERA_UNAVAILABLE, CAMERA_RESUMED, SNOOZE_START, SNOOZE_END, and WARNING_LEVEL_CHANGED, so that I can review behavior after the fact.
53. As the maintainer, I want the JSONL log to be information-equivalent to the Python event log rather than byte-identical, so that I can adopt structured fields (kind, timestamp, payload) without dragging a legacy format forward.
54. As the maintainer, I want backend diagnostic logs (tracing) and the JSONL business log to be separate, so that one doesn't drown the other.
55. As the maintainer, I want the existing Python tests to act as the migration oracle, so that any deviation in posture, snooze, calibration, classifier, display plan, or config is treated as a Rust bug and not a "Rust chose differently" decision.
56. As the maintainer, I want each ported domain module to have Rust unit tests covering at least the same scenarios as its Python counterpart, so that behavioral parity is verifiable in CI.
57. As the maintainer, I want camera and detector layers to be integration-tested via fakes (recorded frames + scripted head-pose sequences), so that domain CI does not require OpenCV or ONNX Runtime.
58. As the maintainer, I want the Tauri Windows installer to bundle ONNX Runtime, the OpenCV runtime, and the chosen ONNX model files, so that a fresh machine never needs to download anything at first run.
59. As the user, I want the installed app to write configuration and logs under `%APPDATA%\eyes\`, so that uninstall doesn't take my settings with it and the install directory stays read-only.
60. As the user, I want uninstall to remove app files but to leave my user configuration alone (with this documented in the README), so that reinstalling preserves my baseline.
61. As the maintainer, I want the installer size recorded as a baseline in the README, so that future bundle-size optimization has a reference point.
62. As the maintainer, I want the legacy Python implementation, tests, packaging, and CI to remain in the repo unchanged through M7, so that the migration oracle stays available and rollback is trivial.
63. As the maintainer, I want M8 to remove all Python source, tests, packaging, and the Python CI workflow, so that the repository ends up as a clean Rust/Tauri project.
64. As the maintainer, I want a new `cargo test` CI job split into a Linux domain-only run and a Windows full run, so that domain regressions are caught fast and only the heavy job needs OpenCV/ONNX.
65. As the maintainer, I want a separate Tauri build CI job that produces an MSI artifact on demand, so that smoke installs are easy without making every PR run the full bundling pipeline.
66. As the maintainer, I want the head-pose detector and the rest of the worker to be wired through traits, so that the worker's behavioral tests can run without ONNX Runtime present.
67. As the user, I want the rewrite to ship as a single MSI installer (NSIS as fallback), so that installation is one familiar Windows step.
68. As the maintainer, I want code signing to be deferred and recorded as a future TODO, so that M7 isn't blocked on certificate procurement.
69. As the maintainer, I want this PRD to be the parent for issue-level breakdowns of M1 through M8, so that each milestone has its own ready-for-agent ticket.

## Implementation Decisions

### Shell, frontend, and process layout

- Tauri 2 desktop application; React + TypeScript + Vite frontend. The frontend stays thin and renders status updates, the settings page, and the reminder window. All business logic lives in Rust.
- Single Tauri Rust crate with internal `domain/`, `monitoring/`, `platform/` modules. No Cargo workspace yet; we can extract `eyes-core` later if a library boundary justifies it.
- `tauri-plugin-single-instance` is mandatory — autostart plus a manual launch must not be able to spawn two camera workers. A second launch focuses the existing window.
- `tauri-plugin-autostart` handles Windows user-level autostart so we don't maintain registry/shortcut code by hand.
- Backend diagnostic logs use `tracing` (or `tauri-plugin-log`); they are kept separate from the JSONL business log.

### Monitoring worker contract

The monitoring worker owns `CameraSource`, the `Detector` trait, the `PostureTickEngine`, and the `CalibrationSession`. It does not depend on any Tauri types so it can be unit-tested with fakes. The Tauri command handler layer adapts between Tauri events/commands and the worker's enums.

The worker contract from the design conversation, encoded as Rust enums:

```rust
enum WorkerCommand {
    Tick,
    UpdateConfig(AppConfig),
    SetCameraIndex(u32),
    StartCalibration { duration_seconds: f64 },
    CancelCalibration,
    PauseSnooze { duration_seconds: Option<u64> },
    ResumeSnooze,
    Shutdown,
}

enum WorkerEvent {
    StatusUpdated(StatusSnapshot),
    PreviewFrame { jpeg: Vec<u8>, width: u32, height: u32 },
    PromptFired(PromptEvent),
    WarningLevelChanged(WarningLevelEvent),
    CameraStateChanged(CameraState),
    CalibrationUpdated(CalibrationState),
    SnoozeUpdated(SnoozeState),
    LogEvent(EventLogEntry),
    Fatal(WorkerError),
}
```

`Tick` is injected externally at 10 Hz so tests can drive deterministic time the same way `PostureTickEngine` does today.

### Tauri command and event schema

Frontend → backend commands (closed list, idempotent, returning `Result<T, AppError>` where `AppError` is a closed Rust enum):

- `get_status() -> Status`
- `get_config() -> AppConfig`
- `update_config(patch: PartialConfig) -> AppConfig`
- `set_camera_index(index: u32)`
- `start_calibration()`
- `cancel_calibration()`
- `pause_snooze(duration_seconds?: u64)`  // omitted = indefinite
- `resume_snooze()`
- `set_language(lang: string)`
- `set_autostart(enabled: bool)`
- `quit_app()`

Backend → frontend events:

- `status-updated` — `Status` snapshot (pose state, last yaw/roll, warning level, snooze state, camera state, calibration state, language).
- `preview-frame` — `{ image_data_url, width, height, captured_at_ms }` on its own channel so it does not bloat status updates.
- `prompt-fired` — `{ kind: "correction" | "good_posture" | "eye_rest" | "corrected", direction?: "left" | "right", message_key, auto_dismiss_ms }`.
- `camera-state-changed` — `{ state: "starting" | "available" | "unavailable", message_key? }`.
- `calibration-updated` — `idle | running | completed | failed` discriminated union.
- `config-updated` — full `AppConfig` (so the UI doesn't have to merge patches).
- `snooze-updated` — `{ state: "inactive" | "active" | "indefinite", until_iso? }`.

### Domain modules (deep, behavior-tested)

- **Classifier** — pure `classify(pose, neutral, thresholds) -> PoseState`.
- **PostureTickEngine** — owns off-axis streak, off-axis repeat interval, facing-time accumulator, presence-time accumulator, and the warning-level state machine; emits `SenseEvent`s per tick.
- **SnoozeEvaluation** — pure `evaluate_snooze(iso, now) -> SnoozeState` for `Inactive | Indefinite | Active | Expired | Malformed`.
- **CalibrationSession** — 5-second sampling lifecycle (start, feed, tick, result) with median pose computation.
- **ConfigStore** — atomic YAML read/write with serde defaults; preserves the existing schema (yaw threshold, roll threshold, neutral yaw, neutral roll, camera index, snooze ISO, sound enabled, autostart enabled, language, off-axis streak threshold, off-axis repeat interval, facing threshold, eye-rest threshold).
- **DisplayPlan** — pure reducer turning `PoseState`/`WarningLevelEvent` history into a UI plan (badge text/colors, banner visibility, auto-dismiss timing).
- **EventLog (JSONL)** — append-only structured log of `AppEventKind` values (STATE_CHANGE, PROMPT_FIRED, CAMERA_UNAVAILABLE, CAMERA_RESUMED, SNOOZE_START, SNOOZE_END, WARNING_LEVEL_CHANGED) to the platform data directory.

### Detection and camera

- Camera capture uses the OpenCV Rust crate and runs in the backend; the frontend never touches `getUserMedia`.
- The `Detector` trait is the seam between detection and the rest of the worker. The first implementation, `OnnxDetector`, uses `ort` and a face-detector + landmark/head-pose model selected by a 2-day spike. The selection is captured in a follow-up ADR.
- The default head-pose path is 2D landmarks fed into OpenCV `solvePnP` to derive yaw/roll. If a one-shot head-pose ONNX model passes the spike, it can replace the landmarks+`solvePnP` path; behavior parity is the contract either way.
- Detection parity is behavioral. The ported Python tests are the oracle for prompt timing, pose classification, and warning-level transitions; raw yaw/roll values are not required to match MediaPipe.
- Sign convention for yaw stays "positive = head turned to user's own right" so calibration semantics carry over.

### Reminders and main window UX

- Reminders are rendered in a dedicated Tauri always-on-top window driven by `prompt-fired`. This continues the rationale of ADR 0004 (we own the prompt surface; the OS notifier is not the product).
- The main window shows a low-FPS encoded preview (JPEG over a Tauri event), the live yaw/roll readout, the pose-state badge, and the warning banner. Inference uses the original frame; preview uses a downscaled copy.
- Closing the main window hides it. Only the tray's `Quit` ends the process. Snooze keeps detection running but silences reminders.

### Calibration

- 5-second worker-owned session, identical semantics to the Python implementation.
- Reminders are silenced while a session is active.
- Result is computed from the median of the collected yaw/roll samples; missing samples = `CalibrationFailed(NoFace)` and the saved neutral is left untouched.
- Cancelling a running session aborts cleanly without writing to config.

### Snooze

- Persistence semantics match the Python `SnoozeManager`: `null` → inactive, `"indefinite"` → indefinite, otherwise an ISO timestamp; naive timestamps are interpreted as UTC; `now == until` counts as expired.
- On startup, an expired snooze clears itself and emits `SNOOZE_END`; an indefinite or future-ISO snooze becomes the live state; a malformed value clears itself and is logged.

### Configuration compatibility

- The Rust `AppConfig` keeps the existing field set so my current YAML loads without manual migration.
- Atomic writes (temp file + rename) match the Python implementation.
- Unknown YAML fields are ignored; missing fields fall back to serde defaults so partial files still load.

### i18n

- Lightweight frontend dictionary covering at least `zh-CN` and `en-US`.
- Backend events carry stable `message_key`s; the frontend maps them to localized strings.
- Switching language refreshes the main window, reminder window, and the tray menu (rebuild if needed).
- No system-language autodetection in the first Rust closure.

### Logging

- JSONL event log under the platform data directory (`%APPDATA%\eyes\` on Windows). One JSON object per line: `{ ts, kind, payload }`.
- Information-equivalent rather than byte-equivalent to the Python event log.
- Failure to write to the log is non-fatal and surfaces through tracing only.

### Packaging, autostart, and platforms

- Windows is the only first-stage platform. macOS and Linux are deferred.
- `cargo tauri build` produces an MSI (NSIS as fallback) that bundles ONNX Runtime, the OpenCV runtime, and the chosen ONNX model files. Nothing is downloaded at first run.
- ONNX models live under bundled resources and are resolved through the Tauri app handle's path API at runtime.
- Configuration and logs live in `%APPDATA%\eyes\`; the install directory stays read-only.
- Code signing is deferred and recorded as a future TODO.
- `models/MANIFEST.toml` (or equivalent) records model filenames, sha256, source URL, and license; the active model version is logged at startup.

### CI

- Existing `linux-build.yml` (Python) is left untouched until M8.
- New `cargo test` job runs on `ubuntu-latest` (domain-only, no OpenCV/ONNX) and on `windows-latest` (full crate). `cargo fmt --check` and `cargo clippy` are part of this job.
- New Tauri build job runs on `windows-latest` for tagged builds or manual dispatch and produces an MSI artifact.
- Domain tests must not depend on OpenCV or ONNX Runtime.

### Migration milestones

The execution is split into eight milestones. Each milestone has its own acceptance checklist in `docs/migration-plan.md`:

- M1 — Tauri skeleton
- M2 — Rust domain core + ported tests
- M3 — Camera preview
- M4 — ONNX detector spike (time-boxed; fallback documented)
- M5 — Monitoring closure (classify → prompts → reminder window → log → snooze/resume/warning levels)
- M6 — Settings + Calibration UI + Windows autostart
- M7 — Windows packaging
- M8 — Legacy cleanup (remove Python source, tests, packaging, and CI; rewrite README)

## Testing Decisions

- **What makes a good test for this rewrite:** assert externally observable behavior — events emitted, config bytes round-tripped, JSONL lines written, prompt sequences fired given a tick stream — never internal field names or call ordering. Tests should drive time deterministically through `Tick` and `dt`, never via real clocks. Tests must not require OpenCV or ONNX Runtime.
- **Modules with required Rust unit tests** (mirror the Python suite — these are the migration oracle):
  - Classifier — must cover the same scenarios as the Python `test_classifier`.
  - PostureTickEngine — must cover off-axis streak/repeat, facing-time praise, presence-time eye rest, and every warning-level transition currently asserted in `test_posture_tick_engine`.
  - SnoozeEvaluation — must cover `Inactive`, `Indefinite`, `Active`, `Expired`, and `Malformed` cases, including naive-timestamp UTC interpretation and the `now == until` boundary.
  - CalibrationSession — must cover start/feed/tick/result lifecycle and median computation including odd/even sample counts.
  - ConfigStore — must cover atomic write semantics, missing-field defaults, unknown-field tolerance, and round-trip with the existing YAML schema.
  - DisplayPlan — must cover the same reducer transitions currently in `test_display_plan` (badge, banner, auto-dismiss).
  - EventLog (JSONL) — must cover serialization of every `AppEventKind` and the append-only contract.
- **Modules covered by integration tests with fakes** (no OpenCV/ONNX dependency):
  - MonitoringWorker — driven by injected `Tick`s, a fake camera that yields recorded BGR frames, and a fake detector returning scripted `HeadPose` sequences. Tests verify the emitted `WorkerEvent` stream for snooze, calibration, warning level, and prompt scenarios.
  - Tauri command/event adapter — verifies that `WorkerEvent` values translate into the documented Tauri event names and payload shapes.
- **Smoke-tested by hand on Windows (not in CI):**
  - OnnxDetector against a real model loaded via `ort` — captured in the M4 spike ADR; does not require an automated Rust test in this PRD.
  - Camera retry on physical disconnect/reconnect.
  - MSI install/uninstall, autostart toggle, single-instance behavior, code-signing prompts (or absence).
- **Prior art to mirror:**
  - Python tests under `tests/` (especially `test_classifier`, `test_posture_tick_engine`, `test_snooze_evaluation`, `test_calibration`, `test_config_store`, `test_display_plan`, `test_event_log`) define the behavioral contract the Rust ports must match.
  - Existing `tests/test_controller.py` and `test_sense_loop.py` show the integration-style assertions the Rust monitoring-worker tests should follow once fakes are in place.

## Out of Scope

- Numeric parity of yaw/roll between the Rust ONNX detector and the Python MediaPipe detector.
- macOS and Linux delivery for the first Rust release. Linux/macOS autostart, packaging, and tray nuances are deferred until Windows is fully validated.
- Audio playback for `sound_enabled`. The flag is preserved in config and UI but does not need to play sound in the first Rust closure.
- Code signing of the Windows installer. Recorded as a future TODO.
- WebView-side camera capture (`getUserMedia`).
- A Cargo workspace split (e.g. extracting `eyes-core` as a library). Stays in a single Tauri crate.
- Replacing the YAML config format with TOML/JSON/SQLite.
- Implementing system-language autodetection for i18n.
- Writing a new always-on-top reminder transparency / multi-monitor / Wayland story beyond what Tauri already provides on Windows.
- Replacing the existing event-log schema with a different file format than JSONL.
- Migrating the Python implementation incrementally via PyO3.

## Further Notes

- This PRD is the parent of milestone-level issues. Each milestone (M1–M8) should be filed as its own ready-for-agent issue against `docs/migration-plan.md` once this PRD is accepted.
- ADRs already in the repo govern how this rewrite behaves:
  - ADR 0001 (yaw/roll only — keep the same axes).
  - ADR 0002 (cumulative-time timers — preserve in PostureTickEngine).
  - ADR 0003 (MediaPipe choice — explicitly superseded by this rewrite for the Rust version).
  - ADR 0004 (custom always-on-top reminder window — continued via the Tauri reminder window).
  - ADR 0005 (this rewrite direction).
- The model-selection spike in M4 must produce ADR 0006 with license, file size, and CPU latency for the chosen ONNX models. If the spike misses its budget, fall back to OpenCV YuNet plus a simpler geometric estimate so M5 is not blocked.
- Snooze persistence semantics, calibration semantics, the warning-level state machine, and the JSONL event kinds are the four areas most likely to silently regress during vibe coding. They are explicitly covered by ported tests for that reason.
- Single-instance behavior is non-negotiable. Without it, autostart plus a manual launch can produce two camera workers fighting for the device.
