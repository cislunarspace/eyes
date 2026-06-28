pub mod app_shell;
pub mod app_state;
pub mod commands;
pub mod domain;
pub mod monitoring;

use std::sync::Mutex;

use app_shell::desktop::{create_tray, handle_second_instance, handle_window_event};
use app_state::AppState;
use commands::{get_config, get_status, set_camera_index, snooze, resume, spawn_worker};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let config = domain::config::ConfigStore::new(dirs::config_dir().unwrap_or_default())
        .load()
        .unwrap_or_default();
    let shared_state = Mutex::new(AppState::new(config));

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            handle_second_instance(app);
        }))
        .manage(shared_state)
        .setup(|app| {
            create_tray(app)?;
            spawn_worker(app.handle().clone());
            Ok(())
        })
        .on_window_event(handle_window_event)
        .invoke_handler(tauri::generate_handler![
            get_status,
            get_config,
            set_camera_index,
            snooze,
            resume,
        ])
        .run(tauri::generate_context!())
        .expect("运行 Eyes 时出错");
}
