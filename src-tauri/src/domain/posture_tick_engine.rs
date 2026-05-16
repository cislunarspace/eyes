use super::classifier::PoseState;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WarningLevel {
    Normal,
    Warning,
    Severe,
    Corrected,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SenseEvent {
    Correction { direction: PoseState },
    GoodPosture,
    EyeRest,
    WarningLevelChanged { level: WarningLevel, direction: Option<String> },
}

const DEFAULT_OFF_AXIS_STREAK_THRESHOLD: f64 = 0.3;
const DEFAULT_OFF_AXIS_REPEAT_INTERVAL: f64 = 10.0;
const DEFAULT_FACING_THRESHOLD: f64 = 300.0;
const DEFAULT_EYEREST_THRESHOLD: f64 = 900.0;

#[derive(Debug, Clone)]
pub struct PostureTickEngine {
    off_axis_streak_threshold: f64,
    off_axis_repeat_interval: f64,
    facing_threshold: f64,
    eyest_threshold: f64,
    off_axis_streak: f64,
    repeat_due_at: Option<f64>,
    last_emit_at: Option<f64>,
    facing_seconds: f64,
    presence_seconds: f64,
    snoozed: bool,
    warning_level: WarningLevel,
    off_axis_continuous_seconds: f64,
    corrected_remaining_seconds: f64,
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
            off_axis_streak: 0.0,
            repeat_due_at: None,
            last_emit_at: None,
            facing_seconds: 0.0,
            presence_seconds: 0.0,
            snoozed: false,
            warning_level: WarningLevel::Normal,
            off_axis_continuous_seconds: 0.0,
            corrected_remaining_seconds: 0.0,
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

    pub fn tick(&mut self, state: PoseState, dt: f64) -> Vec<SenseEvent> {
        let mut events = Vec::new();

        if self.snoozed {
            return events;
        }

        if matches!(state, PoseState::OffAxisLeft | PoseState::OffAxisRight) {
            self.off_axis_streak += dt;
            if self.off_axis_streak >= self.off_axis_streak_threshold {
                if self.last_emit_at.is_none() {
                    self.last_emit_at = Some(self.off_axis_streak);
                    self.repeat_due_at = Some(self.off_axis_streak + self.off_axis_repeat_interval);
                    events.push(SenseEvent::Correction { direction: state });
                } else if self.repeat_due_at.is_some_and(|due_at| self.off_axis_streak >= due_at) {
                    self.repeat_due_at = Some(self.off_axis_streak + self.off_axis_repeat_interval);
                    events.push(SenseEvent::Correction { direction: state });
                }
            }
        } else {
            self.off_axis_streak = 0.0;
            self.repeat_due_at = None;
            self.last_emit_at = None;
        }

        if state == PoseState::FacingScreen {
            self.facing_seconds += dt;
            if self.facing_seconds >= self.facing_threshold {
                self.facing_seconds = 0.0;
                events.push(SenseEvent::GoodPosture);
            }
        }

        if state != PoseState::NoFace {
            self.presence_seconds += dt;
            if self.presence_seconds >= self.eyest_threshold {
                self.presence_seconds = 0.0;
                events.push(SenseEvent::EyeRest);
            }
        }

        match state {
            PoseState::OffAxisLeft | PoseState::OffAxisRight => {
                let direction = if state == PoseState::OffAxisLeft { "left" } else { "right" };
                if matches!(self.warning_level, WarningLevel::Normal | WarningLevel::Corrected) {
                    self.warning_level = WarningLevel::Warning;
                    self.off_axis_continuous_seconds = dt;
                    events.push(SenseEvent::WarningLevelChanged {
                        level: WarningLevel::Warning,
                        direction: Some(direction.to_string()),
                    });
                } else {
                    self.off_axis_continuous_seconds += dt;
                    if self.warning_level == WarningLevel::Warning
                        && self.off_axis_continuous_seconds >= self.off_axis_repeat_interval
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
                if matches!(self.warning_level, WarningLevel::Warning | WarningLevel::Severe) {
                    self.warning_level = WarningLevel::Corrected;
                    self.corrected_remaining_seconds = 2.0;
                    self.off_axis_continuous_seconds = 0.0;
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
                    self.warning_level = WarningLevel::Normal;
                    self.off_axis_continuous_seconds = 0.0;
                    self.corrected_remaining_seconds = 0.0;
                    events.push(SenseEvent::WarningLevelChanged {
                        level: WarningLevel::Normal,
                        direction: None,
                    });
                }
            }
            PoseState::OffAxisOther => {}
        }

        events
    }
}
