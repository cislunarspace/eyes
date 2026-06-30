use serde::{Deserialize, Serialize};
use std::{
    fs, io,
    path::{Path, PathBuf},
};

/// 应用配置，与 Python 端 AppConfig 共享同一份 config.yaml。
///
/// `roll` → `pitch` 重命名兼容：serde 同时接受 `roll_threshold` / `neutral_roll` 和
/// `pitch_threshold` / `neutral_pitch`，序列化始终使用 `pitch` 系列。
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct AppConfig {
    pub yaw_threshold: f64,
    #[serde(alias = "roll_threshold")]
    pub pitch_threshold: f64,
    pub yaw_hysteresis: f64,
    #[serde(alias = "roll_hysteresis")]
    pub pitch_hysteresis: f64,
    pub neutral_yaw: f64,
    #[serde(alias = "neutral_roll")]
    pub neutral_pitch: f64,
    pub camera_index: u32,
    pub language: String,
    pub sound_enabled: bool,
    pub autostart_enabled: bool,
    pub snooze_until_iso: Option<String>,
    pub off_axis_streak_threshold_seconds: f64,
    pub off_axis_repeat_interval_seconds: f64,
    pub facing_threshold_seconds: f64,
    pub eyest_threshold_seconds: f64,
}

impl Default for AppConfig {
    fn default() -> Self {
        use super::defaults;
        Self {
            yaw_threshold: 5.0,
            pitch_threshold: 10.0,
            yaw_hysteresis: 2.5,
            pitch_hysteresis: 5.0,
            neutral_yaw: 0.0,
            neutral_pitch: 0.0,
            camera_index: 0,
            language: "zh-CN".to_string(),
            sound_enabled: true,
            autostart_enabled: false,
            snooze_until_iso: None,
            off_axis_streak_threshold_seconds: defaults::OFF_AXIS_STREAK_THRESHOLD,
            off_axis_repeat_interval_seconds: defaults::OFF_AXIS_REPEAT_INTERVAL,
            facing_threshold_seconds: defaults::FACING_THRESHOLD,
            eyest_threshold_seconds: defaults::EYEREST_THRESHOLD,
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

    pub fn config_dir(&self) -> &Path {
        &self.config_dir
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_config_round_trips_yaml() {
        let config = AppConfig::default();
        let yaml = serde_yaml::to_string(&config).unwrap();
        let parsed: AppConfig = serde_yaml::from_str(&yaml).unwrap();
        assert_eq!(config, parsed);
    }

    #[test]
    fn deserialize_with_legacy_roll_field_names() {
        let yaml = r#"
yaw_threshold: 3.0
roll_threshold: 7.0
neutral_yaw: 1.0
neutral_roll: -2.0
"#;
        let config: AppConfig = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(config.yaw_threshold, 3.0);
        assert_eq!(config.pitch_threshold, 7.0);
        assert_eq!(config.neutral_yaw, 1.0);
        assert_eq!(config.neutral_pitch, -2.0);
    }

    #[test]
    fn deserialize_with_new_pitch_field_names() {
        let yaml = r#"
yaw_threshold: 4.0
pitch_threshold: 8.0
neutral_yaw: 0.5
neutral_pitch: -1.5
"#;
        let config: AppConfig = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(config.pitch_threshold, 8.0);
        assert_eq!(config.neutral_pitch, -1.5);
    }

    #[test]
    fn serialize_uses_pitch_not_roll() {
        let config = AppConfig::default();
        let yaml = serde_yaml::to_string(&config).unwrap();
        assert!(yaml.contains("pitch_threshold"));
        assert!(yaml.contains("neutral_pitch"));
        assert!(!yaml.contains("roll_threshold"));
        assert!(!yaml.contains("neutral_roll"));
    }

    #[test]
    fn missing_fields_use_defaults() {
        let yaml = "yaw_threshold: 2.0\n";
        let config: AppConfig = serde_yaml::from_str(yaml).unwrap();
        assert_eq!(config.yaw_threshold, 2.0);
        assert_eq!(config.pitch_threshold, 10.0); // 默认值
        assert_eq!(config.language, "zh-CN");
        assert!(config.sound_enabled);
    }

    #[test]
    fn round_trip_preserves_advanced_fields() {
        let config = AppConfig {
            facing_threshold_seconds: 600.0,
            eyest_threshold_seconds: 1800.0,
            ..AppConfig::default()
        };
        let yaml = serde_yaml::to_string(&config).unwrap();
        let parsed: AppConfig = serde_yaml::from_str(&yaml).unwrap();
        assert_eq!(parsed.facing_threshold_seconds, 600.0);
        assert_eq!(parsed.eyest_threshold_seconds, 1800.0);
    }

    #[test]
    fn update_modifies_specific_fields() {
        let dir = tempfile::tempdir().unwrap();
        let store = ConfigStore::new(dir.path());
        let result = store.update(|cfg| {
            cfg.yaw_threshold = 7.0;
        });
        let config = result.unwrap();
        assert_eq!(config.yaw_threshold, 7.0);
        assert_eq!(config.pitch_threshold, 10.0);
    }
}
