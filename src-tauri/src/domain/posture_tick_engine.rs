use super::classifier::PoseState;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub enum WarningLevel {
    Normal,
    Warning,
    Severe,
    Corrected,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SenseEvent {
    Correction {
        direction: PoseState,
    },
    GoodPosture,
    EyeRest,
    WarningLevelChanged {
        level: WarningLevel,
        direction: Option<String>,
    },
}

const DEFAULT_OFF_AXIS_STREAK_THRESHOLD: f64 = 0.3;
const DEFAULT_OFF_AXIS_REPEAT_INTERVAL: f64 = 10.0;
const DEFAULT_FACING_THRESHOLD: f64 = 300.0;
const DEFAULT_EYEREST_THRESHOLD: f64 = 900.0;

fn is_yaw_state(state: PoseState) -> bool {
    matches!(state, PoseState::OffAxisLeft | PoseState::OffAxisRight)
}

fn is_pitch_state(state: PoseState) -> bool {
    matches!(state, PoseState::HeadUp | PoseState::HeadDown)
}

fn direction_label(state: PoseState) -> &'static str {
    match state {
        PoseState::OffAxisLeft => "left",
        PoseState::OffAxisRight => "right",
        PoseState::HeadUp => "up",
        PoseState::HeadDown => "down",
        _ => "",
    }
}

/// 单轴 off-axis 跟踪状态：streak 计时、重复提醒、警告升级 FSM。
#[derive(Debug, Clone)]
struct OffAxisState {
    streak: f64,
    repeat_due_at: Option<f64>,
    last_emit_at: Option<f64>,
    warning_level: WarningLevel,
    continuous_seconds: f64,
    corrected_remaining_seconds: f64,
}

impl OffAxisState {
    fn new() -> Self {
        Self {
            streak: 0.0,
            repeat_due_at: None,
            last_emit_at: None,
            warning_level: WarningLevel::Normal,
            continuous_seconds: 0.0,
            corrected_remaining_seconds: 0.0,
        }
    }

    fn reset_streak(&mut self) {
        self.streak = 0.0;
        self.repeat_due_at = None;
        self.last_emit_at = None;
    }

    fn reset_warning(&mut self) {
        self.warning_level = WarningLevel::Normal;
        self.continuous_seconds = 0.0;
        self.corrected_remaining_seconds = 0.0;
    }

    /// 偏离连续时长追踪。
    fn update_streak(
        &mut self,
        state: PoseState,
        dt: f64,
        streak_threshold: f64,
        repeat_interval: f64,
        events: &mut Vec<SenseEvent>,
    ) {
        if is_off_for_self(state) {
            self.streak += dt;
            if self.streak >= streak_threshold {
                if self.last_emit_at.is_none() {
                    self.last_emit_at = Some(self.streak);
                    self.repeat_due_at = Some(self.streak + repeat_interval);
                    events.push(SenseEvent::Correction { direction: state });
                } else if self
                    .repeat_due_at
                    .is_some_and(|due_at| self.streak >= due_at)
                {
                    self.repeat_due_at = Some(self.streak + repeat_interval);
                    events.push(SenseEvent::Correction { direction: state });
                }
            }
        } else {
            self.reset_streak();
        }
    }

    /// Warning 级别 FSM：Normal → Warning → Severe → Corrected → Normal。
    fn update_warning_level(
        &mut self,
        state: PoseState,
        dt: f64,
        repeat_interval: f64,
        events: &mut Vec<SenseEvent>,
    ) {
        let direction = direction_label(state);
        match state {
            _ if is_off_for_self(state) => {
                if matches!(
                    self.warning_level,
                    WarningLevel::Normal | WarningLevel::Corrected
                ) {
                    self.warning_level = WarningLevel::Warning;
                    self.continuous_seconds = dt;
                    events.push(SenseEvent::WarningLevelChanged {
                        level: WarningLevel::Warning,
                        direction: Some(direction.to_string()),
                    });
                } else {
                    self.continuous_seconds += dt;
                    if self.warning_level == WarningLevel::Warning
                        && self.continuous_seconds >= repeat_interval
                    {
                        self.warning_level = WarningLevel::Severe;
                        events.push(SenseEvent::WarningLevelChanged {
                            level: WarningLevel::Severe,
                            direction: Some(direction.to_string()),
                        });
                    }
                }
            }
            PoseState::FacingScreen => {
                if matches!(
                    self.warning_level,
                    WarningLevel::Warning | WarningLevel::Severe
                ) {
                    self.warning_level = WarningLevel::Corrected;
                    self.corrected_remaining_seconds = 2.0;
                    self.continuous_seconds = 0.0;
                    events.push(SenseEvent::WarningLevelChanged {
                        level: WarningLevel::Corrected,
                        direction: None,
                    });
                } else if self.warning_level == WarningLevel::Corrected {
                    self.corrected_remaining_seconds -= dt;
                    if self.corrected_remaining_seconds <= 0.0 {
                        self.warning_level = WarningLevel::Normal;
                        self.corrected_remaining_seconds = 0.0;
                        events.push(SenseEvent::WarningLevelChanged {
                            level: WarningLevel::Normal,
                            direction: None,
                        });
                    }
                }
            }
            PoseState::NoFace => {
                if matches!(
                    self.warning_level,
                    WarningLevel::Warning | WarningLevel::Severe | WarningLevel::Corrected
                ) {
                    self.reset_warning();
                    events.push(SenseEvent::WarningLevelChanged {
                        level: WarningLevel::Normal,
                        direction: None,
                    });
                }
            }
            _ => {}
        }
    }

    /// 处理单轴完整 tick：streak + warning。
    fn tick(
        &mut self,
        state: PoseState,
        dt: f64,
        streak_threshold: f64,
        repeat_interval: f64,
    ) -> Vec<SenseEvent> {
        let mut events = Vec::new();
        // 不属于本轴且非通用状态 → 静默忽略
        if !is_applicable(state) {
            return events;
        }
        self.update_streak(state, dt, streak_threshold, repeat_interval, &mut events);
        self.update_warning_level(state, dt, repeat_interval, &mut events);
        events
    }
}

/// 判断状态是否属于本轴的 off-axis。
fn is_off_for_self(state: PoseState) -> bool {
    // 调用前已通过 is_applicable 过滤，此处只需匹配所有 off-axis 状态
    matches!(
        state,
        PoseState::OffAxisLeft
            | PoseState::OffAxisRight
            | PoseState::HeadUp
            | PoseState::HeadDown
    )
}

/// 通用状态（两轴共享）：FacingScreen、NoFace。
fn is_applicable(state: PoseState) -> bool {
    is_yaw_state(state) || is_pitch_state(state) || matches!(state, PoseState::FacingScreen | PoseState::NoFace)
}

#[derive(Debug, Clone)]
pub struct PostureTickEngine {
    off_axis_streak_threshold: f64,
    off_axis_repeat_interval: f64,
    facing_threshold: f64,
    eyest_threshold: f64,
    facing_seconds: f64,
    presence_seconds: f64,
    snoozed: bool,
    yaw_oa: OffAxisState,
    pitch_oa: OffAxisState,
}

impl Default for PostureTickEngine {
    fn default() -> Self {
        Self::new(None, None, None, None)
    }
}

impl PostureTickEngine {
    pub fn new(
        off_axis_streak_threshold_seconds: Option<f64>,
        off_axis_repeat_interval_seconds: Option<f64>,
        facing_threshold_seconds: Option<f64>,
        eyest_threshold_seconds: Option<f64>,
    ) -> Self {
        Self {
            off_axis_streak_threshold: off_axis_streak_threshold_seconds
                .unwrap_or(DEFAULT_OFF_AXIS_STREAK_THRESHOLD),
            off_axis_repeat_interval: off_axis_repeat_interval_seconds
                .unwrap_or(DEFAULT_OFF_AXIS_REPEAT_INTERVAL),
            facing_threshold: facing_threshold_seconds.unwrap_or(DEFAULT_FACING_THRESHOLD),
            eyest_threshold: eyest_threshold_seconds.unwrap_or(DEFAULT_EYEREST_THRESHOLD),
            facing_seconds: 0.0,
            presence_seconds: 0.0,
            snoozed: false,
            yaw_oa: OffAxisState::new(),
            pitch_oa: OffAxisState::new(),
        }
    }

    pub fn is_snoozed(&self) -> bool {
        self.snoozed
    }

    pub fn snooze(&mut self) {
        self.snoozed = true;
    }

    pub fn resume(&mut self) {
        self.snoozed = false;
    }

    /// 当前综合警告级别（取两轴中更严重者）。
    pub fn warning_level(&self) -> WarningLevel {
        match (self.yaw_oa.warning_level, self.pitch_oa.warning_level) {
            (WarningLevel::Severe, _) | (_, WarningLevel::Severe) => WarningLevel::Severe,
            (WarningLevel::Warning, _) | (_, WarningLevel::Warning) => WarningLevel::Warning,
            (WarningLevel::Corrected, _) | (_, WarningLevel::Corrected) => WarningLevel::Corrected,
            _ => WarningLevel::Normal,
        }
    }

    /// 双轴 tick。
    ///
    /// - yaw_state / pitch_state 各自独立生成 Correction 和 WarningLevelChanged 事件。
    /// - GoodPosture 仅在两轴均 FacingScreen 时累积。
    /// - EyeRest 基于有脸时间（两轴均非 NoFace）。
    pub fn tick(
        &mut self,
        yaw_state: PoseState,
        pitch_state: PoseState,
        dt: f64,
    ) -> Vec<SenseEvent> {
        let mut events = Vec::new();

        if self.snoozed {
            return events;
        }

        // 各轴独立处理 off-axis streak + 警告升级
        events.extend(self.yaw_oa.tick(
            yaw_state,
            dt,
            self.off_axis_streak_threshold,
            self.off_axis_repeat_interval,
        ));
        events.extend(self.pitch_oa.tick(
            pitch_state,
            dt,
            self.off_axis_streak_threshold,
            self.off_axis_repeat_interval,
        ));

        // GoodPosture：两轴均 FacingScreen 才累积，其他情况暂停（不重置）
        let both_facing =
            yaw_state == PoseState::FacingScreen && pitch_state == PoseState::FacingScreen;
        if both_facing {
            self.facing_seconds += dt;
            if self.facing_seconds >= self.facing_threshold {
                self.facing_seconds = 0.0;
                events.push(SenseEvent::GoodPosture);
            }
        }

        // EyeRest：两轴均有脸即累积
        let any_face = yaw_state != PoseState::NoFace && pitch_state != PoseState::NoFace;
        if any_face {
            self.presence_seconds += dt;
            if self.presence_seconds >= self.eyest_threshold {
                self.presence_seconds = 0.0;
                events.push(SenseEvent::EyeRest);
            }
        }

        events
    }
}
