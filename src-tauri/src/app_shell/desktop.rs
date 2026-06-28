use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    App, AppHandle, Manager, Runtime, WindowEvent,
};

use super::contract::{
    close_requested_decision, second_instance_decision, CloseDecision, SecondInstanceDecision,
    MAIN_WINDOW_LABEL, MENU_QUIT_ID, MENU_SETTINGS_ID, MENU_SHOW_ID, TRAY_ID,
};

pub fn focus_main_window<R: Runtime>(app: &AppHandle<R>) {
    if let Some(window) = app.get_webview_window(MAIN_WINDOW_LABEL) {
        let _ = window.show();
        let _ = window.unminimize();
        let _ = window.set_focus();
    }
}

pub fn handle_second_instance<R: Runtime>(app: &AppHandle<R>) {
    match second_instance_decision() {
        SecondInstanceDecision::FocusMainWindow => focus_main_window(app),
    }
}

pub fn handle_window_event<R: Runtime>(window: &tauri::Window<R>, event: &WindowEvent) {
    if let WindowEvent::CloseRequested { api, .. } = event {
        match close_requested_decision() {
            CloseDecision::HideToTray => {
                api.prevent_close();
                let _ = window.hide();
            }
        }
    }
}

pub fn create_tray(app: &App) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, MENU_SHOW_ID, "显示", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, MENU_SETTINGS_ID, "设置", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, MENU_QUIT_ID, "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &settings, &quit])?;

    let icon = app
        .default_window_icon()
        .cloned()
        .expect("configured app icon should be available for tray");

    TrayIconBuilder::with_id(TRAY_ID)
        .icon(icon)
        .tooltip("Eyes")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            MENU_SHOW_ID | MENU_SETTINGS_ID => focus_main_window(app),
            MENU_QUIT_ID => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                focus_main_window(tray.app_handle());
            }
        })
        .build(app)?;

    Ok(())
}
