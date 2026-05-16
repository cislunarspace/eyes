# Rust rewrite migration plan

This plan is the execution layer for [ADR 0005](adr/0005-rust-rewrite-direction.md). It splits the full Rust/Tauri rewrite into eight runnable milestones with explicit acceptance checklists. Python source stays in the repo until M8.

## Architecture summary

```text
src-tauri/src/
├── main.rs                  # Tauri builder, plugin wiring, single-instance + autostart
├── app_state.rs             # Shared state, command/event channels, latest snapshot
├── commands.rs              # Tauri commands (UI -> backend)
├── events.rs                # WorkerEvent -> Tauri emit translation
├── config.rs                # Atomic YAML load/save, serde defaults
├── log.rs                   # JSONL event log (separate from tracing)
├── i18n_keys.rs             # Stable backend message keys
├── monitoring/
│   ├── mod.rs
│   ├── worker.rs            # WorkerCommand/Event loop, owns Camera + Detector + Engine
│   ├── camera.rs            # OpenCV capture, retry, BGR frame
│   ├── detector.rs          # Detector trait + OnnxDetector impl
│   ├── pose.rs              # solvePnP + sign convention helpers
│   └── preview.rs           # Downscale + JPEG encode for UI preview
├── domain/
│   ├── mod.rs
│   ├── classifier.rs        # NeutralPose, Thresholds, classify()
│   ├── posture_tick_engine.rs
│   ├── snooze.rs            # evaluate_snooze + state machine
│   ├── calibration.rs       # CalibrationSession, compute_median_pose
│   └── display_plan.rs      # Pure UI projection used by the renderer
└── platform/
    ├── mod.rs
    ├── autostart_windows.rs # Wrapper over tauri-plugin-autostart
    └── tray.rs              # Tray menu, language refresh, snooze items

frontend/                    # React + TS + Vite
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── pages/
│   │   ├── MainView.tsx
│   │   └── Settings.tsx
│   ├── windows/
│   │   └── Reminder.tsx
│   ├── ipc/                 # invoke wrappers + event listeners
│   └── i18n/
│       ├── zh-CN.ts
│       └── en-US.ts
└── index.html

models/                      # ONNX models bundled into installer
docs/                        # ADRs + this plan
src/, tests/, main.py, ...   # Legacy Python (deleted in M8)
```

## Tauri commands (UI -> backend)

```ts
get_status()                            -> Status
get_config()                            -> AppConfig
update_config(patch: PartialConfig)     -> AppConfig
set_camera_index(index: number)         -> void
start_calibration()                     -> void
cancel_calibration()                    -> void
pause_snooze(duration_seconds?: number) -> void   // null/undefined = indefinite
resume_snooze()                         -> void
set_language(lang: "zh-CN" | "en-US")   -> void
set_autostart(enabled: boolean)         -> void
quit_app()                              -> void
```

Commands are idempotent. Errors are returned as `Result<T, AppError>` where `AppError` is a closed Rust enum that does not leak internal details to the frontend.

## Backend events (backend -> UI)

```ts
"status-updated"          Status
"preview-frame"           { image_data_url, width, height, captured_at_ms }
"prompt-fired"            { kind, direction?, message_key, auto_dismiss_ms }
"camera-state-changed"    { state: "starting"|"available"|"unavailable", message_key? }
"calibration-updated"     CalibrationState  // idle | running | completed | failed
"config-updated"          AppConfig
"snooze-updated"          { state: "inactive"|"active"|"indefinite", until_iso? }
```

Heavy preview frames travel on their own event so they never bloat `status-updated`.

## Worker contract (internal Rust)

```rust
enum WorkerCommand {
    Tick,                                          // injected by 10 Hz timer or tests
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

The worker uses no Tauri types directly. `events.rs` adapts `WorkerEvent` into Tauri `emit_all`/`emit` calls so the worker stays unit-testable with a fake camera and fake detector.

## Milestones and acceptance

### M1 — Tauri skeleton

- [ ] `cargo tauri dev` opens an empty React main window on Windows.
- [ ] Tray icon shown.
- [ ] Closing the main window hides it; the process keeps running.
- [ ] Tray menu shows Show / Settings (placeholder) / Quit.
- [ ] Quit truly exits.
- [ ] `tauri-plugin-single-instance` enabled — second launch focuses the existing window.

### M2 — Rust domain core + ported tests

- [ ] `domain::classifier` Rust unit tests cover the cases in `tests/test_classifier.py`.
- [ ] `domain::posture_tick_engine` mirrors `tests/test_posture_tick_engine.py`.
- [ ] `domain::snooze::evaluate_snooze` mirrors `tests/test_snooze_evaluation.py`, including malformed/indefinite/expired/active.
- [ ] `domain::calibration` mirrors `tests/test_calibration.py` (median pose plus session lifecycle).
- [ ] `domain::display_plan` mirrors `tests/test_display_plan.py`.
- [ ] `config::ConfigStore` reads and writes `~/.config/eyes/config.yaml` (or platform equivalent), uses serde defaults for missing fields, writes atomically (temp + rename).
- [ ] `cargo test` is green on Linux and Windows.

### M3 — Camera preview

- [ ] Worker opens camera index 0 via OpenCV Rust crate.
- [ ] Main window displays a low-FPS preview through the `preview-frame` event.
- [ ] Disconnecting the camera emits `camera-state-changed: unavailable`; UI shows the unavailable banner.
- [ ] 5-second retry restores the preview without restarting the app.
- [ ] Missing camera at startup does not crash the app.
- [ ] Closing the main window keeps the worker ticking; reopening continues to receive frames.

### M4 — ONNX detector spike

- [ ] `monitoring::detector::Detector` trait defined; `OnnxDetector` is the first implementation.
- [ ] Selected face detector + landmark/head-pose model recorded in `docs/adr/0006-onnx-detector-choice.md` with license, size, and CPU latency.
- [ ] Model files included via `tauri.conf.json` `bundle.resources`; runtime resolves them through `app_handle.path()`.
- [ ] Detector returns `Option<HeadPose { yaw, roll }>`; missing face returns `None`.
- [ ] Yaw sign convention matches the README contract (positive = head turned to user's own right).
- [ ] Single-frame CPU inference on a Windows desktop class machine < 60 ms.
- [ ] Detector + landmark assets together < 30 MB.
- [ ] Five manual poses (forward, left turn, right turn, look up, look down) produce the correct sign direction post-calibration.
- [ ] 1-minute continuous inference is stable (no panic, no obvious leak).
- [ ] Spike is time-boxed at 2 working days. If no candidate passes, fall back to OpenCV YuNet plus a simpler geometric estimate so M5 is not blocked.

### M5 — Monitoring closure

- [ ] Worker integrates Detector → Classifier → PostureTickEngine → events.
- [ ] Main window readout shows live yaw / roll / pose state.
- [ ] All `WarningLevel` transitions (NORMAL → WARNING → SEVERE → CORRECTED → NORMAL) are reproducible by hand on the local machine.
- [ ] `prompt-fired` drives the Tauri reminder window for correction / good_posture / eye_rest / corrected.
- [ ] Reminder window is always-on-top and auto-dismisses.
- [ ] Snooze 30 min, 1 hour, indefinite all silence reminders correctly; tray and UI state reflect snooze status.
- [ ] Resume re-enables reminders.
- [ ] App restart correctly recovers snooze state for active / expired / indefinite / malformed cases (matches `evaluate_snooze` outcomes).
- [ ] JSONL log captures STATE_CHANGE / PROMPT_FIRED / WARNING_LEVEL_CHANGED / CAMERA_UNAVAILABLE / CAMERA_RESUMED / SNOOZE_START / SNOOZE_END.

### M6 — Settings + Calibration UI + Windows autostart

- [ ] Settings page edits yaw threshold, roll threshold, camera index, language, sound_enabled, autostart_enabled.
- [ ] Advanced timing fields (`off_axis_streak_threshold_seconds`, `off_axis_repeat_interval_seconds`, `facing_threshold_seconds`, `eyest_threshold_seconds`) round-trip through YAML.
- [ ] Saving sends `update_config`; worker applies new thresholds and classifier neutral immediately.
- [ ] Changing camera index reopens the camera and the retry path stays correct.
- [ ] Switching language refreshes main window, reminder window, and tray menu text.
- [ ] Calibration button starts a 5-second session; UI shows remaining seconds and sample count.
- [ ] Reminders are silenced during calibration. Completed calibration writes `neutral_yaw` / `neutral_roll` and the engine adopts the new neutral immediately.
- [ ] No-face for the entire window emits `CalibrationFailed(NoFace)` and leaves config unchanged.
- [ ] Cancel calibration aborts cleanly.
- [ ] `tauri-plugin-autostart` toggles Windows user-level autostart; relaunch on next login is verified by hand.
- [ ] `sound_enabled` persists and is reflected in the UI; playback can remain unimplemented.

### M7 — Windows packaging

- [ ] `cargo tauri build` produces an installable MSI (NSIS acceptable as fallback).
- [ ] Installed app launches from the Start menu.
- [ ] OpenCV (`opencv_world*.dll`) and ONNX Runtime (`onnxruntime.dll`) ship inside the installer; no “DLL not found” errors on a clean machine.
- [ ] ONNX model files ship inside the installer and are located via `app_handle.path()`.
- [ ] Configuration and logs are written to `%APPDATA%\eyes\`, never to the install directory.
- [ ] Uninstall removes app files; user config is preserved (documented in README).
- [ ] Installer size recorded in README as a baseline for future optimisation.
- [ ] Verified on at least one clean Windows machine or VM.
- [ ] `models/MANIFEST.toml` lists model filenames, sha256, source URL, and license; startup logs the active model version.

### M8 — Legacy cleanup

- [ ] Rust app passes M1 through M7.
- [ ] Remove `src/`, `tests/`, `main.py`, `eyes.spec`, `eyes-linux.spec`, `pyproject.toml`, `uv.lock`, `.venv/`, `scripts/build*.py`.
- [ ] Remove `.github/workflows/linux-build.yml` (Python pipeline).
- [ ] Rewrite `README.md` and `README_zh.md` for the Rust/Tauri version; archive the old README at `docs/legacy/README-pyside.md` if useful.
- [ ] Migration commit makes it easy to find the cutover point.
- [ ] Repository root contains only Rust, Tauri, frontend, models, docs.

## Continuous integration

| Pipeline | Trigger | Runner | Purpose |
| --- | --- | --- | --- |
| `linux-build.yml` (existing) | push, PR | ubuntu-latest | Legacy Python build/tests; untouched until M8 |
| `rust-test.yml` (new) | push, PR | ubuntu-latest + windows-latest | `cargo fmt --check`, `cargo clippy`, `cargo test`. Linux job covers `domain/*` only and must not depend on OpenCV/ONNX. Windows job covers full crate. |
| `tauri-build.yml` (new) | manual + tag | windows-latest | `cargo tauri build`, uploads MSI artifact for manual smoke tests. Not required to be green for PRs that don't touch packaging. |

Domain tests are designed to run without OpenCV or ONNX so they stay fast and portable. Camera/detector code uses a `Detector` trait so the integration layer can be tested with a fake detector when needed.

## Plugin choices

- `tauri-plugin-autostart` — Windows user-level autostart.
- `tauri-plugin-single-instance` — required; prevents autostart + manual launch from spawning two camera workers.
- `tauri` core — tray, windows, IPC, bundling.
- `tauri-plugin-log` or `tracing` + `tracing-subscriber` — backend diagnostic log (separate from the JSONL business log).

## Migration oracle

The Python suite under `tests/` is the migration oracle for behavior. For each domain module ported in M2 the corresponding Rust test must cover at least the same scenarios. Behavioral drift is treated as a Rust bug.

For the camera/detector layers, integration tests use:

- A fake camera that yields recorded BGR frames.
- A fake detector that returns scripted `HeadPose` sequences.

This keeps `cargo test` green without needing OpenCV/ONNX in CI runners.
