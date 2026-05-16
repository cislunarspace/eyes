# 0005 — Full Rust rewrite via Tauri 2

Eyes is being fully rewritten in Rust as a Tauri 2 desktop app. The Python / PySide6 / MediaPipe implementation is replaced rather than wrapped. The migration is a direct full-rewrite using vibe coding, executed in runnable milestones rather than a single big-bang patch. Functional equivalence with the existing app takes priority over matching the current PySide UI exactly.

## Considered Options

- **Gradual core extraction (PyO3 bindings to a small Rust core, keep Python shell)** — rejected: the user explicitly wants to migrate the whole app and learn Rust. Mixing FFI plus PySide adds friction without reducing risk.
- **egui / Slint native Rust UI** — rejected: tray, always-on-top reminder window, settings dialog, autostart, and Windows packaging are noticeably easier on Tauri's WebView shell. UI parity is not required, so a thin web frontend is enough.
- **Qt for Rust / C++ Qt bridge** — rejected: closest to the existing PySide layout but the heaviest build/distribution path of the candidates and the most painful to vibe-code through.
- **MediaPipe C++ bindings for head-pose detection** — rejected: official Rust support is immature and would dominate the migration timeline. ONNX models via `ort` are far easier to integrate and bundle.

## Decision

- **Shell:** Tauri 2.
- **Frontend:** React + TypeScript + Vite. Thin UI; business logic stays in Rust.
- **Repo layout:** single Tauri crate (`src-tauri/`) with internal `domain/`, `monitoring/`, `platform/` modules. No workspace yet.
- **Process model:** one monitoring worker owns `CameraSource`, `Detector`, `PostureTickEngine`. Worker is driven by external `Tick` commands at 10 Hz. Worker emits `WorkerEvent`s; an adapter layer translates them into Tauri events. The worker is decoupled from Tauri types so it is unit-testable in isolation.
- **Camera + image processing:** OpenCV Rust crate. Capture and preview encoding run in the Rust backend, not in the WebView.
- **Head-pose detection:** ONNX face detector + landmark (or direct head-pose) model loaded via `ort`. Default head-pose path is 2D landmarks plus OpenCV `solvePnP`. A dedicated 2-day spike picks the model; selection is recorded in `0006-onnx-detector-choice.md` (to be written) with license, size, and latency notes. Detection parity is **behavioral**, not numeric: pose classification and reminders match the Python version; raw yaw/roll values are not required to match MediaPipe.
- **Reminders:** dedicated Tauri always-on-top reminder window, replacing the PySide overlay. System notifications are a future enhancement, not the primary mechanism (consistent with [0004](0004-custom-floating-window-over-os-toast.md)).
- **Main window preview:** required, but allowed to be a low-FPS encoded preview (JPEG over a Tauri event). Inference uses the original frame; preview uses a downscaled copy.
- **Tray lifecycle:** mandatory. Closing the main window hides it; only `Quit` ends the process. Snooze keeps detection running but silences reminders. Snooze persistence semantics (`null` / `"indefinite"` / future ISO with malformed/expired handling) are preserved exactly from the Python version.
- **Calibration:** worker-side 5-second median-pose session, identical semantics to the Python implementation. Reminders are paused while calibration is active. Progress and outcome are emitted as events.
- **Configuration:** existing YAML format and on-disk path are preserved. Rust uses `serde` with defaults for missing fields and atomic write (temp file + rename). Advanced timing fields stay readable from YAML even when not exposed in the simplified Settings UI.
- **Event log:** preserved in semantics, but written as JSONL (information-equivalent rather than byte-compatible).
- **i18n:** `zh-CN` and `en-US`, lightweight frontend dictionary plus stable backend message keys. Settings change rebuilds tray menu and refreshes any open windows.
- **Sound:** `sound_enabled` is preserved as config and UI but does not require playback in the first Rust closure.
- **Autostart:** real Windows user-level autostart is required for the first Rust version. Implementation uses `tauri-plugin-autostart`. macOS/Linux autostart is deferred.
- **Single instance:** `tauri-plugin-single-instance` is mandatory because autostart plus manual launch can otherwise spawn two workers competing for the camera.
- **Platforms:** Windows is the only first-stage required platform. macOS and Linux follow later.
- **Packaging:** all assets (ONNX model files, ONNX Runtime DLL, OpenCV DLL) are bundled into the installer. Nothing is downloaded at runtime. Configs and logs go to `%APPDATA%\eyes\`. Code signing is deferred.
- **Tests as oracle:** existing Python tests are the migration oracle for behavioral parity. Rust unit tests in `domain/*` mirror the Python suite (`test_classifier`, `test_posture_tick_engine`, `test_snooze_evaluation`, `test_calibration`, `test_config_store`, `test_display_plan`). UI / camera / ONNX layers get integration smoke tests instead of attempted line-by-line parity.
- **Coexistence:** Python source, tests, packaging, and CI stay in the repository unchanged until the Rust app reaches functional closure (M7). Cleanup happens in M8.
- **CI:** legacy Python CI is left untouched. New `cargo test` job runs on Linux (domain only, no OpenCV/ONNX) and Windows (full). A separate Tauri build job produces an MSI artifact on Windows.

## Milestones

1. **M1 — Tauri skeleton.** Window, tray, close-to-tray, quit.
2. **M2 — Rust domain core + ported tests.** Classifier, posture engine, snooze, calibration, config store.
3. **M3 — Camera preview.** OpenCV capture, low-FPS preview, retry on disconnect.
4. **M4 — ONNX detector spike.** Model selection, `Detector` trait, 2D landmarks + solvePnP path, behavior verification.
5. **M5 — Monitoring closure.** classify → posture engine → reminder window → JSONL log → snooze/resume/warning levels.
6. **M6 — Settings + Calibration UI + Windows autostart.**
7. **M7 — Windows packaging.** MSI/NSIS, bundled DLLs and model, validated on a clean Windows machine.
8. **M8 — Legacy cleanup.** Remove Python source/tests/packaging/CI, rewrite README, leave only the Rust/Tauri stack.

## Consequences

- The migration cannot be reduced to a single PR; it is a sequence of runnable milestones with their own acceptance checklists ([migration-plan.md](../migration-plan.md)).
- OpenCV and ONNX Runtime DLL bundling on Windows is real packaging work and must be solved before M7 can complete.
- Behavior-level acceptance means the Python test suite is the source of truth for posture, snooze, calibration, and event-log semantics. Any deviation is treated as a Rust bug, not as “the Rust version chose a different behavior.”
- Skipping renderer-side camera access (`getUserMedia`) keeps background monitoring reliable but means preview frames must be encoded and shipped over the IPC channel.
- The reminder window decision continues the spirit of [0004](0004-custom-floating-window-over-os-toast.md): we own the prompt surface; the OS notifier is not the product.
- The MediaPipe rationale captured in [0003](0003-mediapipe-for-head-pose.md) is superseded for the Rust version. The new head-pose source is ONNX + `solvePnP`; behavior parity is the contract, not yaw/roll numerical equivalence.
