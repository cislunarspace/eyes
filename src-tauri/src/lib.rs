pub mod app_shell;
pub mod app_state;
pub mod commands;
pub mod domain;
pub mod monitoring;

use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex, RwLock};

use app_shell::desktop::{create_tray, handle_second_instance, handle_window_event, rebuild_tray};
use app_state::AppState;
use commands::{
    cancel_calibration, feed_calibration, get_config, get_status, resume, set_camera_index,
    set_config, snooze, spawn_worker, start_calibration,
};
use domain::calibration::CalibrationSession;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let config = domain::config::ConfigStore::new(dirs::config_dir().unwrap_or_default())
        .load()
        .unwrap_or_default();
    let language = config.language.clone();
    let shared_config = Arc::new(RwLock::new(config.clone()));
    let shared_calibration = Arc::new(Mutex::new(CalibrationSession::new(5.0)));
    let shared_snooze = Arc::new(AtomicBool::new(false));
    let shared_state = Mutex::new(AppState::new(config));

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            handle_second_instance(app);
        }))
        .manage(shared_state)
        .manage(shared_config.clone())
        .manage(shared_calibration.clone())
        .manage(shared_snooze.clone())
        .setup(move |app| {
            create_tray(app, &language)?;
            spawn_worker(
                app.handle().clone(),
                shared_config,
                shared_calibration,
                shared_snooze,
            );
            Ok(())
        })
        .on_window_event(handle_window_event)
        .invoke_handler(tauri::generate_handler![
            get_status,
            get_config,
            set_config,
            set_camera_index,
            snooze,
            resume,
            start_calibration,
            feed_calibration,
            cancel_calibration,
        ])
        .run(tauri::generate_context!())
        .expect("运行 Eyes 时出错");
}
