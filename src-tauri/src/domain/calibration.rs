#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PoseSample {
    pub yaw: f64,
    pub roll: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CalibrationResult {
    pub yaw: f64,
    pub roll: f64,
    pub sample_count: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct EmptySamples;

const COUNTDOWN_EPSILON: f64 = 1e-9;

pub fn compute_median_pose(samples: &[PoseSample]) -> Result<PoseSample, EmptySamples> {
    if samples.is_empty() {
        return Err(EmptySamples);
    }

    let mut sorted: Vec<PoseSample> = samples.to_vec();
    sorted.sort_by(|a, b| a.yaw.partial_cmp(&b.yaw).unwrap_or(std::cmp::Ordering::Equal));

    let len = sorted.len();
    if len == 1 {
        return Ok(sorted[0]);
    }

    if len % 2 == 1 {
        return Ok(sorted[len / 2]);
    }

    let mid1 = &sorted[len / 2 - 1];
    let mid2 = &sorted[len / 2];
    Ok(PoseSample {
        yaw: (mid1.yaw + mid2.yaw) / 2.0,
        roll: (mid1.roll + mid2.roll) / 2.0,
    })
}

#[derive(Debug, Clone)]
pub struct CalibrationSession {
    duration_seconds: f64,
    countdown: f64,
    samples: Vec<PoseSample>,
    active: bool,
    finished: bool,
}

impl CalibrationSession {
    pub fn new(duration_seconds: f64) -> Self {
        Self {
            duration_seconds,
            countdown: 0.0,
            samples: Vec::new(),
            active: false,
            finished: false,
        }
    }

    pub fn is_active(&self) -> bool {
        self.active
    }

    pub fn countdown_seconds(&self) -> f64 {
        self.countdown
    }

    pub fn sample_count(&self) -> usize {
        self.samples.len()
    }

    pub fn start(&mut self) {
        self.samples.clear();
        self.countdown = self.duration_seconds;
        self.active = true;
        self.finished = false;
    }

    pub fn feed(&mut self, yaw: f64, roll: f64) {
        if !self.active {
            return;
        }
        self.samples.push(PoseSample { yaw, roll });
    }

    pub fn tick(&mut self, dt: f64) {
        if !self.active {
            return;
        }
        self.countdown -= dt;
        if self.countdown <= COUNTDOWN_EPSILON {
            self.countdown = 0.0;
            self.active = false;
            self.finished = true;
        }
    }

    pub fn result(&self) -> Option<CalibrationResult> {
        if !self.finished || self.samples.is_empty() {
            return None;
        }
        let median = compute_median_pose(&self.samples).ok()?;
        Some(CalibrationResult {
            yaw: median.yaw,
            roll: median.roll,
            sample_count: self.samples.len(),
        })
    }
}
