// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use std::time::Duration;
use tauri::image::Image;
use tauri::menu::MenuBuilder;
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, WindowEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const API_HOST: &str = "127.0.0.1:8000";
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const APP_ICON_PNG: &[u8] = include_bytes!("../../../assets/icons/glimpse_256.png");

struct AppState {
    backend_child: Mutex<Option<Child>>,
    quitting: AtomicBool,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_child: Mutex::new(None),
            quitting: AtomicBool::new(false),
        }
    }
}

fn backend_is_running() -> bool {
    let addr: SocketAddr = match API_HOST.parse() {
        Ok(addr) => addr,
        Err(_) => return false,
    };

    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn project_root() -> Option<PathBuf> {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..");
    root.canonicalize().ok()
}

fn backend_autostart_disabled() -> bool {
    matches!(
        std::env::var("GLIMPSE_SKIP_BACKEND_AUTOSTART"),
        Ok(value) if value == "1"
    )
}

fn build_backend_command(app: &AppHandle) -> Option<Command> {
    #[cfg(debug_assertions)]
    {
        let _ = app;
        let root = project_root()?;
        let python_executable = std::env::var("GLIMPSE_PYTHON")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "python".to_string());
        let mut command = Command::new(python_executable);
        command.arg("main_api.py").current_dir(root);
        return Some(command);
    }

    #[cfg(not(debug_assertions))]
    {
        let resource_dir = app.path().resource_dir().ok()?;
        let sidecar_dir = resource_dir.join("binaries").join("python-backend");

        #[cfg(target_os = "windows")]
        let sidecar_exe = sidecar_dir.join("python-backend.exe");
        #[cfg(not(target_os = "windows"))]
        let sidecar_exe = sidecar_dir.join("python-backend");

        if !sidecar_exe.exists() {
            eprintln!(
                "Bundled backend sidecar not found: {}",
                sidecar_exe.display()
            );
            return None;
        }

        let mut command = Command::new(sidecar_exe);
        command.current_dir(&sidecar_dir);
        Some(command)
    }
}

fn spawn_backend_if_needed(app: &AppHandle) -> Option<Child> {
    if backend_autostart_disabled() {
        return None;
    }

    if backend_is_running() {
        return None;
    }

    let mut command = build_backend_command(app)?;

    #[cfg(target_os = "windows")]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }

    match command.spawn() {
        Ok(child) => Some(child),
        Err(error) => {
            eprintln!("Failed to spawn backend automatically: {error}");
            None
        }
    }
}

fn with_main_window<F>(app: &AppHandle, callback: F)
where
    F: FnOnce(tauri::WebviewWindow),
{
    if let Some(window) = app.get_webview_window("main") {
        callback(window);
    }
}

fn show_main_window(app: &AppHandle) {
    with_main_window(app, |window| {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    });
}

fn hide_main_window(app: &AppHandle) {
    with_main_window(app, |window| {
        let _ = window.hide();
    });
}

fn stop_backend_process(state: &AppState) {
    if let Ok(mut guard) = state.backend_child.lock() {
        if let Some(child) = guard.as_mut() {
            let _ = child.kill();
        }
        *guard = None;
    }
}

fn quit_application(app: &AppHandle) {
    let state = app.state::<AppState>();
    state.quitting.store(true, Ordering::SeqCst);
    stop_backend_process(&state);
    app.exit(0);
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    quit_application(&app);
}

#[tauri::command]
fn hide_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.minimize().map_err(|error| error.to_string())
}

#[tauri::command]
fn focus_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.unminimize().map_err(|error| error.to_string())?;
    window.show().map_err(|error| error.to_string())?;
    window.set_focus().map_err(|error| error.to_string())
}

#[tauri::command]
fn minimize_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.minimize().map_err(|error| error.to_string())
}

#[tauri::command]
fn start_drag_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.start_dragging().map_err(|error| error.to_string())
}

#[tauri::command]
fn toggle_maximize_window(window: tauri::WebviewWindow) -> Result<(), String> {
    let is_maximized = window.is_maximized().map_err(|error| error.to_string())?;
    if is_maximized {
        window.unmaximize().map_err(|error| error.to_string())
    } else {
        window.maximize().map_err(|error| error.to_string())
    }
}

#[tauri::command]
fn is_window_maximized(window: tauri::WebviewWindow) -> Result<bool, String> {
    window.is_maximized().map_err(|error| error.to_string())
}

fn load_app_icon() -> Option<Image<'static>> {
    Image::from_bytes(APP_ICON_PNG).ok().map(Image::to_owned)
}

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            quit_app,
            hide_window,
            focus_window,
            minimize_window,
            start_drag_window,
            toggle_maximize_window,
            is_window_maximized
        ])
        .setup(|app| {
            if let Some(child) = spawn_backend_if_needed(app.handle()) {
                let state = app.state::<AppState>();
                let guard = state.backend_child.lock();
                if let Ok(mut guard) = guard {
                    *guard = Some(child);
                }
            }

            let app_icon = load_app_icon();
            if let (Some(window), Some(icon)) = (app.get_webview_window("main"), app_icon.clone()) {
                let _ = window.set_icon(icon);
            }

            let tray_menu = MenuBuilder::new(app)
                .text("show", "显示主窗口")
                .text("hide", "隐藏到托盘")
                .separator()
                .text("quit", "退出 Glimpse")
                .build()?;

            let tray_builder = TrayIconBuilder::with_id("main-tray")
                .tooltip("Glimpse")
                .menu(&tray_menu);

            if let Some(icon) = app_icon {
                tray_builder.icon(icon).build(app)?;
            } else if let Some(icon) = app.default_window_icon().cloned() {
                tray_builder.icon(icon).build(app)?;
            } else {
                tray_builder.build(app)?;
            }

            show_main_window(app.handle());
            Ok(())
        })
        .on_menu_event(|app, event| match event.id().as_ref() {
            "show" => show_main_window(app),
            "hide" => hide_main_window(app),
            "quit" => quit_application(app),
            _ => {}
        })
        .on_window_event(|window, event| {
            if let WindowEvent::CloseRequested { api, .. } = event {
                let state = window.app_handle().state::<AppState>();
                if !state.quitting.load(Ordering::SeqCst) {
                    api.prevent_close();
                    if window.emit("glimpse://close-requested", ()).is_err() {
                        let _ = window.hide();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
