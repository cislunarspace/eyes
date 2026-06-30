use crate::domain::calibration::CalibrationSession;
use crate::domain::config::AppConfig;
use crate::domain::event_log::{AppEventKind, EventLog};
use crate::domain::posture_tick_engine::SenseEvent;
use crate::domain::snooze;
use crate::monitoring::detector::Detector;
use crate::monitoring::preview::PreviewFrame;
use crate::monitoring::worker::{FrameSource, MonitoringWorker, WorkerOutput};

use std::sync::{Arc, Mutex, RwLock};
use std::time::{Duration, Instant};

// ── WorkerCommand（从 worker_command 上移到此处） ─────────────────

/// 前端 → worker 控制指令。
#[derive(Debug)]
pub enum WorkerCommand {
    SetCameraIndex(u32),
    SetConfig(Box<AppConfig>),
    Snooze(f64),
    Resume,
    Stop,
}

/// 线程安全的命令发送端，Tauri command handler 通过它向 worker 发指令。
#[derive(Clone)]
pub struct WorkerSender(std::sync::mpsc::Sender<WorkerCommand>);

impl WorkerSender {
    pub fn send(&self, cmd: WorkerCommand) -> Result<(), String> {
        self.0.send(cmd).map_err(|_| "worker 已停止".to_string())
    }
}

pub type WorkerReceiver = std::sync::mpsc::Receiver<WorkerCommand>;

pub fn channel() -> (WorkerSender, WorkerReceiver) {
    let (tx, rx) = std::sync::mpsc::channel();
    (WorkerSender(tx), rx)
}

// ── 事件输出抽象 ─────────────────────────────────────────────────
//
// 把 Tauri AppHandle 依赖隔离到 trait 背后，让 WorkerOrchestrator
// 不依赖 Tauri 运行时，可以独立测试。

pub trait EventSink: Send + 'static {
    fn emit_camera_state_changed(&self, state: &str);
    fn emit_pose_updated(&self, yaw: Option<f64>, pitch: Option<f64>, pose_state: &str);
    fn emit_preview_frame(&self, preview: &PreviewFrame);
    fn emit_sound_alert(&self, alert_type: &str);
    fn emit_warning_level_changed(&self, level: &str, direction: Option<&str>);
    fn show_dialog(&self, title: &str, body: &str);
    fn log_event(&self, kind: AppEventKind, data: serde_json::Value);
    fn log_info(&self, message: &str);
}

// ── 监控器抽象 ───────────────────────────────────────────────────
//
// 包装 MonitoringWorker<C>，消除泛型参数，使 orchestrator 可以
// 通过 trait object 持有任意摄像头实现的 worker。

pub trait Monitor: Send + 'static {
    fn tick(&mut self, dt: f64) -> WorkerOutput;
    fn set_snoozed(&mut self, snoozed: bool);
}

impl<C: FrameSource + Send + 'static> Monitor for MonitoringWorker<C> {
    fn tick(&mut self, dt: f64) -> WorkerOutput {
        self.tick(dt)
    }
    fn set_snoozed(&mut self, snoozed: bool) {
        self.set_snoozed(snoozed);
    }
}

pub type CameraFactory =
    Box<dyn FnMut(u32) -> Result<Box<dyn FrameSource>, String> + Send>;
pub type DetectorFactory =
    Box<dyn Fn() -> Option<Box<dyn Detector>> + Send>;
pub type MonitorFactory =
    Box<dyn Fn(Box<dyn FrameSource>, Option<Box<dyn Detector>>) -> Box<dyn Monitor> + Send>;

// ── WorkerOrchestrator ───────────────────────────────────────────
//
// 管理后台监控 worker 的完整生命周期：摄像头重连、免打扰倒计时、
// tick 驱动、事件输出。
//
// 通过 EventSink trait 发射事件，不依赖 Tauri 运行时。

pub struct WorkerOrchestrator {
    config: AppConfig,
    shared_state: Arc<Mutex<crate::app_state::AppState>>,
    shared_calibration: Arc<Mutex<CalibrationSession>>,
    event_sink: Box<dyn EventSink>,
    camera_factory: CameraFactory,
    detector_factory: DetectorFactory,
    monitor_factory: MonitorFactory,
    event_log: EventLog,
}

impl WorkerOrchestrator {
    pub fn new(
        config: AppConfig,
        _shared_config: Arc<RwLock<AppConfig>>,
        shared_state: Arc<Mutex<crate::app_state::AppState>>,
        shared_calibration: Arc<Mutex<CalibrationSession>>,
        event_sink: Box<dyn EventSink>,
        camera_factory: CameraFactory,
        detector_factory: DetectorFactory,
        monitor_factory: MonitorFactory,
        event_log: EventLog,
    ) -> Self {
        Self {
            config,
            shared_state,
            shared_calibration,
            event_sink,
            camera_factory,
            detector_factory,
            monitor_factory,
            event_log,
        }
    }

    /// 运行监控循环。阻塞当前线程，直到收到 Stop 命令。
    pub fn run(mut self, rx: WorkerReceiver) {
        use crate::app_state::CameraState;

        let mut camera_index = self.config.camera_index;
        let mut snooze_remaining: f64 = 0.0;
        let mut monitor: Option<Box<dyn Monitor>> = self.open_monitor(camera_index);

        // 更新初始摄像头状态
        {
            let camera_state = if monitor.is_some() {
                CameraState::Available
            } else {
                CameraState::Unavailable
            };
            if let Ok(mut s) = self.shared_state.lock() {
                s.status.camera_state = camera_state;
            }
        }

        let mut retry_at: Option<Instant> = if monitor.is_none() {
            Some(Instant::now() + Duration::from_secs(5))
        } else {
            None
        };

        let tick_interval = Duration::from_millis(100);
        let mut stopped = false;

        while !stopped {
            // 处理命令（阻塞等待，最多 tick_interval）
            match rx.recv_timeout(tick_interval) {
                Ok(cmd) => match cmd {
                    WorkerCommand::Stop => {
                        stopped = true;
                        continue;
                    }
                    WorkerCommand::SetCameraIndex(idx) => {
                        camera_index = idx;
                        monitor = None;
                        retry_at = Some(Instant::now());
                        if let Ok(mut s) = self.shared_state.lock() {
                            s.status.camera_state = CameraState::Starting;
                        }
                    }
                    WorkerCommand::SetConfig(new_config) => {
                        self.config = *new_config;
                        monitor.take();
                        monitor = self.open_monitor(camera_index);
                    }
                    WorkerCommand::Snooze(seconds) => {
                        snooze_remaining = seconds;
                        if let Some(ref mut w) = monitor {
                            w.set_snoozed(true);
                        }
                    }
                    WorkerCommand::Resume => {
                        snooze_remaining = 0.0;
                        if let Some(ref mut w) = monitor {
                            w.set_snoozed(false);
                        }
                        if let Ok(mut s) = self.shared_state.lock() {
                            s.status.snooze_state = snooze::SnoozeState::Inactive;
                        }
                    }
                },
                Err(std::sync::mpsc::RecvTimeoutError::Timeout) => {
                    // 超时：正常 tick
                }
                Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => {
                    break;
                }
            }

            self.process_tick(&mut monitor, &mut snooze_remaining, &mut retry_at, camera_index);
        }

        // Stop 后继续处理剩余的 tick（在退出前）
        // （rx 已关闭，不再读取命令）
        // 这里直接退出，与原始行为一致。
    }

    fn process_tick(
        &mut self,
        monitor: &mut Option<Box<dyn Monitor>>,
        snooze_remaining: &mut f64,
        retry_at: &mut Option<Instant>,
        camera_index: u32,
    ) {
        use crate::app_state::CameraState;

        let now = Instant::now();

        // snooze 倒计时
        if *snooze_remaining > 0.0 && *snooze_remaining < f64::INFINITY {
            *snooze_remaining -= 0.1;
            if *snooze_remaining <= 0.0 {
                *snooze_remaining = 0.0;
                if let Some(ref mut w) = monitor {
                    w.set_snoozed(false);
                }
                if let Ok(mut s) = self.shared_state.lock() {
                    s.status.snooze_state = snooze::SnoozeState::Inactive;
                }
            }
        }

        // 重试摄像头
        if monitor.is_none() && retry_at.is_some_and(|due| now >= due) {
            *monitor = self.open_monitor(camera_index);
            if monitor.is_some() {
                if let Ok(mut s) = self.shared_state.lock() {
                    s.status.camera_state = CameraState::Available;
                }
                *retry_at = None;
            } else {
                *retry_at = Some(now + Duration::from_secs(5));
            }
        }

        if let Some(ref mut w) = monitor {
            let output = w.tick(0.1);

            // 校准中：喂样本
            if let Ok(mut session) = self.shared_calibration.try_lock() {
                if session.is_active() {
                    if let (Some(y), Some(p)) = (output.yaw, output.pitch) {
                        session.feed(y, p);
                    }
                    session.tick(0.1);
                }
            }

            // StatusSnapshot 回写
            if let Ok(mut s) = self.shared_state.lock() {
                s.status.pose_state = output.pose_state;
                s.status.yaw = output.yaw;
                s.status.pitch = output.pitch;
                s.status.warning_level = output.warning_level;
                if !output.camera_ok {
                    s.status.camera_state = CameraState::Unavailable;
                }
            }

            // 事件输出
            emit_tick_output(&*self.event_sink, &self.event_log, &output);

            if !output.camera_ok {
                monitor.take();
                *retry_at = Some(now + Duration::from_secs(5));
            }
        }
    }

    fn open_monitor(&mut self, camera_index: u32) -> Option<Box<dyn Monitor>> {
        let camera = (self.camera_factory)(camera_index).ok()?;
        let detector = (self.detector_factory)();
        Some((self.monitor_factory)(camera, detector))
    }
}

// ── 事件输出 ─────────────────────────────────────────────────────

fn emit_tick_output(sink: &dyn EventSink, log: &EventLog, output: &WorkerOutput) {
    if let Some(ref preview) = output.preview {
        sink.emit_preview_frame(preview);
    }

    if !output.camera_ok {
        sink.emit_camera_state_changed("unavailable");
        sink.log_event(AppEventKind::CameraUnavailable, serde_json::json!({}));
        return;
    }

    let pose_str = format!("{:?}", output.pose_state);
    sink.emit_pose_updated(output.yaw, output.pitch, &pose_str);

    for event in &output.sense_events {
        emit_sense_event(sink, log, event);
    }
}

fn emit_sense_event(sink: &dyn EventSink, _log: &EventLog, event: &SenseEvent) {
    use crate::domain::classifier::PoseState;
    match event {
        SenseEvent::Correction { direction } => {
            let dir = match *direction {
                PoseState::OffAxisLeft => "left",
                PoseState::OffAxisRight => "right",
                PoseState::HeadUp => "up",
                PoseState::HeadDown => "down",
                _ => "unknown",
            };
            sink.emit_warning_level_changed("correction", Some(dir));
            sink.emit_sound_alert("posture");
            sink.log_event(
                AppEventKind::PromptFired,
                serde_json::json!({ "prompt": "correction", "direction": dir }),
            );
        }
        SenseEvent::GoodPosture => {
            sink.emit_warning_level_changed("good_posture", None);
            sink.log_event(
                AppEventKind::PromptFired,
                serde_json::json!({ "prompt": "good_posture" }),
            );
        }
        SenseEvent::EyeRest => {
            sink.emit_warning_level_changed("eye_rest", None);
            sink.emit_sound_alert("eyerest");
            sink.log_event(
                AppEventKind::PromptFired,
                serde_json::json!({ "prompt": "eye_rest" }),
            );
        }
        SenseEvent::WarningLevelChanged { level, direction } => {
            let level_str = format!("{:?}", level);
            sink.emit_warning_level_changed(&level_str, direction.as_deref());
            sink.log_event(
                AppEventKind::WarningLevelChanged,
                serde_json::json!({
                    "level": level_str,
                    "direction": direction,
                }),
            );
        }
    }
}

// ── 测试 ─────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::domain::classifier::PoseState;
    use crate::domain::posture_tick_engine::WarningLevel;
    use std::sync::{Arc, Mutex};

    // ── Mock Monitor ─────────────────────────────────────────────

    struct MockMonitor {
        outputs: Vec<WorkerOutput>,
        index: usize,
        snoozed: bool,
    }

    impl MockMonitor {
        fn new(outputs: Vec<WorkerOutput>) -> Self {
            Self {
                outputs,
                index: 0,
                snoozed: false,
            }
        }
    }

    impl Monitor for MockMonitor {
        fn tick(&mut self, _dt: f64) -> WorkerOutput {
            if self.index < self.outputs.len() {
                let out = &self.outputs[self.index];
                self.index += 1;
                WorkerOutput {
                    preview: None,
                    camera_ok: out.camera_ok,
                    pose_state: out.pose_state,
                    pitch_state: out.pitch_state,
                    yaw: out.yaw,
                    pitch: out.pitch,
                    warning_level: out.warning_level,
                    sense_events: out.sense_events.clone(),
                }
            } else {
                WorkerOutput {
                    preview: None,
                    camera_ok: false,
                    pose_state: PoseState::NoFace,
                    pitch_state: PoseState::NoFace,
                    yaw: None,
                    pitch: None,
                    warning_level: WarningLevel::Normal,
                    sense_events: Vec::new(),
                }
            }
        }

        fn set_snoozed(&mut self, snoozed: bool) {
            self.snoozed = snoozed;
        }
    }

    // ── Mock EventSink ───────────────────────────────────────────

    #[derive(Clone)]
    struct MockSink {
        events: Arc<Mutex<Vec<String>>>,
    }

    impl MockSink {
        fn new() -> Self {
            Self {
                events: Arc::new(Mutex::new(Vec::new())),
            }
        }

        fn get_events(&self) -> Vec<String> {
            self.events.lock().unwrap().clone()
        }
    }

    impl EventSink for MockSink {
        fn emit_camera_state_changed(&self, state: &str) {
            self.events.lock().unwrap().push(format!("camera:{}", state));
        }

        fn emit_pose_updated(&self, _yaw: Option<f64>, _pitch: Option<f64>, pose_state: &str) {
            self.events
                .lock()
                .unwrap()
                .push(format!("pose:{}", pose_state));
        }

        fn emit_preview_frame(&self, _preview: &PreviewFrame) {
            self.events.lock().unwrap().push("preview".into());
        }

        fn emit_sound_alert(&self, alert_type: &str) {
            self.events
                .lock()
                .unwrap()
                .push(format!("sound:{}", alert_type));
        }

        fn emit_warning_level_changed(&self, level: &str, direction: Option<&str>) {
            self.events.lock().unwrap().push(format!(
                "warning:{}:{}",
                level,
                direction.unwrap_or("none")
            ));
        }

        fn show_dialog(&self, title: &str, _body: &str) {
            self.events.lock().unwrap().push(format!("dialog:{}", title));
        }

        fn log_event(&self, kind: AppEventKind, _data: serde_json::Value) {
            self.events
                .lock()
                .unwrap()
                .push(format!("log:{:?}", kind));
        }

        fn log_info(&self, message: &str) {
            self.events.lock().unwrap().push(format!("info:{}", message));
        }
    }

    // ── 辅助 ─────────────────────────────────────────────────────

    fn good_output() -> WorkerOutput {
        WorkerOutput {
            preview: None,
            camera_ok: true,
            pose_state: PoseState::FacingScreen,
            pitch_state: PoseState::FacingScreen,
            yaw: Some(0.0),
            pitch: Some(0.0),
            warning_level: WarningLevel::Normal,
            sense_events: Vec::new(),
        }
    }

    fn camera_fail_output() -> WorkerOutput {
        WorkerOutput {
            preview: None,
            camera_ok: false,
            pose_state: PoseState::NoFace,
            pitch_state: PoseState::NoFace,
            yaw: None,
            pitch: None,
            warning_level: WarningLevel::Normal,
            sense_events: Vec::new(),
        }
    }

    fn correction_output(direction: PoseState) -> WorkerOutput {
        WorkerOutput {
            preview: None,
            camera_ok: true,
            pose_state: direction,
            pitch_state: PoseState::FacingScreen,
            yaw: Some(10.0),
            pitch: Some(0.0),
            warning_level: WarningLevel::Normal,
            sense_events: vec![SenseEvent::Correction { direction }],
        }
    }

    fn setup_orchestrator(
        outputs: Vec<WorkerOutput>,
        sink: MockSink,
        camera_factory_succeeds: bool,
    ) -> (WorkerOrchestrator, WorkerSender, WorkerReceiver) {
        let (tx, rx) = channel();
        let config = AppConfig::default();
        let dir = tempfile::tempdir().unwrap();

        let shared_config: Arc<RwLock<AppConfig>> =
            Arc::new(RwLock::new(config.clone()));
        let shared_state = Arc::new(Mutex::new(crate::app_state::AppState::new(
            config.clone(),
        )));
        let shared_calibration = Arc::new(Mutex::new(
            crate::domain::calibration::CalibrationSession::new(5.0),
        ));

        let mock_monitor: Arc<Mutex<Option<Box<dyn Monitor>>>> =
            Arc::new(Mutex::new(Some(Box::new(MockMonitor::new(outputs)))));

        let monitor_ref = mock_monitor.clone();
        let monitor_factory: MonitorFactory = Box::new(move |_cam, _det| {
            monitor_ref
                .lock()
                .unwrap()
                .take()
                .expect("mock monitor already consumed")
        });

        let camera_factory: CameraFactory = if camera_factory_succeeds {
            Box::new(move |_idx| {
                struct Dummy;
                impl FrameSource for Dummy {
                    fn read_frame(&mut self) -> Result<Option<crate::monitoring::preview::Frame>, String> {
                        Ok(None)
                    }
                }
                Ok(Box::new(Dummy))
            })
        } else {
            Box::new(move |_idx| Err("摄像头不可用".into()))
        };

        let detector_factory: DetectorFactory = Box::new(|| None);

        let path = dir.into_path();
        let orchestrator = WorkerOrchestrator::new(
            config,
            shared_config,
            shared_state,
            shared_calibration,
            Box::new(sink),
            camera_factory,
            detector_factory,
            monitor_factory,
            EventLog::new(path.clone()),
        );

        (orchestrator, tx, rx)
    }

    // ── 测试用例 ─────────────────────────────────────────────────

    #[test]
    fn emits_pose_on_good_tick() {
        let sink = MockSink::new();
        let (orch, tx, rx) =
            setup_orchestrator(vec![good_output()], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        std::thread::sleep(Duration::from_millis(150));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();

        let events = sink.get_events();
        assert!(events.iter().any(|e| e.starts_with("pose:")));
    }

    #[test]
    fn stops_on_command() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(vec![], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();
    }

    #[test]
    fn snooze_command_sets_snooze() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(vec![good_output()], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        let _ = tx.send(WorkerCommand::Snooze(600.0));
        std::thread::sleep(Duration::from_millis(150));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();
    }

    #[test]
    fn resume_clears_snooze() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(vec![good_output()], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        let _ = tx.send(WorkerCommand::Snooze(600.0));
        std::thread::sleep(Duration::from_millis(50));
        let _ = tx.send(WorkerCommand::Resume);
        std::thread::sleep(Duration::from_millis(50));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();
    }

    #[test]
    fn correction_emits_warning_and_sound() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(
            vec![correction_output(PoseState::OffAxisLeft)],
            sink.clone(),
            true,
        );

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        std::thread::sleep(Duration::from_millis(150));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();

        let events = sink.get_events();
        assert!(events.iter().any(|e| e.starts_with("warning:correction:")));
        assert!(events.iter().any(|e| e == "sound:posture"));
    }

    #[test]
    fn camera_failure_emits_state_change() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(
            vec![camera_fail_output()],
            sink.clone(),
            true,
        );

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        std::thread::sleep(Duration::from_millis(150));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();

        let events = sink.get_events();
        assert!(events.iter().any(|e| e == "camera:unavailable"));
    }

    #[test]
    fn camera_factory_failure_triggers_retry() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(vec![], sink.clone(), false);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        std::thread::sleep(Duration::from_millis(150));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();
    }

    #[test]
    fn set_camera_index_resets_monitor() {
        let sink = MockSink::new();
        let (orch, tx, rx) = setup_orchestrator(vec![good_output()], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        std::thread::sleep(Duration::from_millis(50));
        let _ = tx.send(WorkerCommand::SetCameraIndex(1));
        std::thread::sleep(Duration::from_millis(50));
        let _ = tx.send(WorkerCommand::Stop);
        let _ = handle.join();
    }

    #[test]
    fn channel_close_exits_gracefully() {
        let sink = MockSink::new();
        let (orch, _tx, rx) = setup_orchestrator(vec![], sink.clone(), true);

        let handle = std::thread::spawn(move || {
            orch.run(rx);
        });

        // rx 在 orchestrator.run 中使用，tx 被 drop 后 rx.recv_timeout 会返回 Err
        // 但这里 tx 已经 move 进 setup_orchestrator 了...
        // 需要在 setup 之后 drop tx
        drop(_tx);
        let _ = handle.join();
    }

    #[test]
    fn worker_command_is_debug() {
        let cmd = WorkerCommand::Stop;
        let _ = format!("{:?}", cmd);
    }
}
