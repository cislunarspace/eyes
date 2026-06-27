use serde::{Deserialize, Serialize};
use std::{
    fs, io,
    path::{Path, PathBuf},
};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub yaw_threshold: f64,
    pub roll_threshold: f64,
    pub neutral_yaw: f64,
    pub neutral_roll: f64,
    pub camera_index: u32,
    pub snooze_until_iso: Option<String>,
    pub sound_enabled: bool,
    pub autostart_enabled: bool,
    pub language: String,
    pub off_axis_streak_threshold_seconds: f64,
    pub off_axis_repeat_interval_seconds: f64,
    pub facing_threshold_seconds: f64,
    pub eyest_threshold_seconds: f64,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            yaw_threshold: 1.0,
            roll_threshold: 90.0,
            neutral_yaw: 0.0,
            neutral_roll: 0.0,
            camera_index: 0,
            snooze_until_iso: None,
            sound_enabled: false,
            autostart_enabled: false,
            language: "zh-CN".to_string(),
            off_axis_streak_threshold_seconds: 0.3,
            off_axis_repeat_interval_seconds: 10.0,
            facing_threshold_seconds: 300.0,
            eyest_threshold_seconds: 900.0,
        }
    }
}

#[derive(Debug, Clone)]
pub struct ConfigStore {
    config_dir: PathBuf,
}

impl ConfigStore {
    pub fn new(config_dir: impl AsRef<Path>) -> Self {
        Self {
            config_dir: config_dir.as_ref().to_path_buf(),
        }
    }

    pub fn load(&self) -> io::Result<AppConfig> {
        fs::create_dir_all(&self.config_dir)?;
        let path = self.config_path();
        if !path.exists() {
            let config = AppConfig::default();
            self.save(&config)?;
            return Ok(config);
        }

        let content = fs::read_to_string(path)?;
        if content.trim().is_empty() {
            return Ok(AppConfig::default());
        }

        Ok(serde_yaml::from_str(&content).unwrap_or_default())
    }

    pub fn save(&self, config: &AppConfig) -> io::Result<()> {
        fs::create_dir_all(&self.config_dir)?;
        let path = self.config_path();
        let temp_path = path.with_extension("yaml.tmp");
        let content = serde_yaml::to_string(config)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        fs::write(&temp_path, content)?;
        fs::rename(temp_path, path)?;
        Ok(())
    }

    pub fn update(&self, update: impl FnOnce(&mut AppConfig)) -> io::Result<AppConfig> {
        let mut config = self.load()?;
        update(&mut config);
        self.save(&config)?;
        Ok(config)
    }

    fn config_path(&self) -> PathBuf {
        self.config_dir.join("config.yaml")
    }
}
