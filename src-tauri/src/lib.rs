pub mod app_shell;
pub mod domain;
pub mod monitoring;

use app_shell::desktop::{create_tray, handle_second_instance, handle_window_event};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            handle_second_instance(app);
        }))
        .setup(|app| {
            create_tray(app)?;
            Ok(())
        })
        .on_window_event(handle_window_event)
        .run(tauri::generate_context!())
        .expect("error while running Eyes");
}
