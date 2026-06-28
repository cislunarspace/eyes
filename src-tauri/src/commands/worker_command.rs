use std::sync::mpsc;

/// 前端命令 → worker 线程的控制指令。
pub enum WorkerCommand {
    /// 切换摄像头索引，worker 立即重新打开。
    SetCameraIndex(u32),
    /// 暂停提醒，`seconds` 秒后自动恢复。`f64::INFINITY` = 不限时。
    Snooze(f64),
    /// 恢复提醒。
    Resume,
}

/// 线程安全的命令发送端，Tauri command handler 通过它向 worker 发指令。
#[derive(Clone)]
pub struct WorkerSender(mpsc::Sender<WorkerCommand>);

impl WorkerSender {
    pub fn send(&self, cmd: WorkerCommand) -> Result<(), String> {
        self.0.send(cmd).map_err(|_| "worker 已停止".to_string())
    }
}

pub fn channel() -> (WorkerSender, mpsc::Receiver<WorkerCommand>) {
    let (tx, rx) = mpsc::channel();
    (WorkerSender(tx), rx)
}
