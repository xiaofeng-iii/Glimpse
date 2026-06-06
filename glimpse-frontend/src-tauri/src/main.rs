// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::Serialize;
#[cfg(not(debug_assertions))]
use std::fmt::Write as FmtWrite;
#[cfg(debug_assertions)]
use std::io::{Read, Write};
use std::net::SocketAddr;
#[cfg(not(debug_assertions))]
use std::net::TcpListener;
#[cfg(debug_assertions)]
use std::net::TcpStream;
#[cfg(not(debug_assertions))]
use std::path::Path;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
#[cfg(debug_assertions)]
use std::time::Duration;
use tauri::image::Image;
use tauri::menu::MenuBuilder;
use tauri::tray::{MouseButton, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, WindowEvent};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const DEV_API_ORIGIN: &str = "http://127.0.0.1:8000";
#[cfg(not(debug_assertions))]
const LOOPBACK_HOST: &str = "127.0.0.1";
#[cfg(debug_assertions)]
const BACKEND_IDENTITY_MARKER: &str = "Glimpse API";
#[cfg(all(target_os = "windows", not(debug_assertions)))]
const BACKEND_PROCESS_NAME: &str = "python-backend.exe";
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const APP_ICON_PNG: &[u8] = include_bytes!("../../../assets/icons/glimpse_256.png");

struct AppState {
    backend_child: Mutex<Option<Child>>,
    backend_runtime: Mutex<BackendRuntime>,
    quitting: AtomicBool,
}

#[derive(Clone, Serialize)]
struct BackendRuntime {
    origin: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    token: Option<String>,
}

impl Default for BackendRuntime {
    fn default() -> Self {
        Self {
            origin: DEV_API_ORIGIN.to_string(),
            token: None,
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            backend_child: Mutex::new(None),
            backend_runtime: Mutex::new(BackendRuntime::default()),
            quitting: AtomicBool::new(false),
        }
    }
}

fn api_addr(origin: &str) -> Option<SocketAddr> {
    origin.strip_prefix("http://")?.parse().ok()
}

#[cfg(debug_assertions)]
fn connect_api_port(origin: &str) -> Option<TcpStream> {
    let addr: SocketAddr = match api_addr(origin) {
        Some(addr) => addr,
        None => return None,
    };

    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).ok()
}

#[cfg(debug_assertions)]
fn backend_port_is_open(origin: &str) -> bool {
    connect_api_port(origin).is_some()
}

#[cfg(debug_assertions)]
fn glimpse_backend_is_running(runtime: &BackendRuntime) -> bool {
    let mut stream = match connect_api_port(&runtime.origin) {
        Some(stream) => stream,
        None => return false,
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(700)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));

    let host = runtime.origin.trim_start_matches("http://");
    let auth_header = runtime
        .token
        .as_ref()
        .map(|token| format!("X-Glimpse-Auth: {token}\r\n"))
        .unwrap_or_default();
    let request = format!(
        "GET /api/health HTTP/1.1\r\nHost: {host}\r\n{auth_header}Connection: close\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).is_err() {
        return false;
    }

    let mut response = String::new();
    if stream.read_to_string(&mut response).is_err() {
        return false;
    }

    response.contains(BACKEND_IDENTITY_MARKER)
}

#[cfg(not(debug_assertions))]
fn allocate_loopback_port() -> Option<u16> {
    let listener = TcpListener::bind((LOOPBACK_HOST, 0)).ok()?;
    listener.local_addr().ok().map(|addr| addr.port())
}

#[cfg(not(debug_assertions))]
fn generate_auth_token() -> String {
    let mut bytes = [0_u8; 32];
    if getrandom::fill(&mut bytes).is_err() {
        let fallback = format!(
            "{}:{}:{:?}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|value| value.as_nanos())
                .unwrap_or_default(),
            std::thread::current().id()
        );
        bytes.fill(0);
        for (index, byte) in fallback.as_bytes().iter().enumerate() {
            bytes[index % bytes.len()] ^= *byte;
        }
    }

    let mut token = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        let _ = write!(&mut token, "{byte:02x}");
    }
    token
}

fn backend_runtime_for_launch() -> BackendRuntime {
    #[cfg(debug_assertions)]
    {
        BackendRuntime::default()
    }

    #[cfg(not(debug_assertions))]
    {
        let port = allocate_loopback_port().unwrap_or(8000);
        BackendRuntime {
            origin: format!("http://{LOOPBACK_HOST}:{port}"),
            token: Some(generate_auth_token()),
        }
    }
}

#[cfg(debug_assertions)]
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

fn build_backend_command(app: &AppHandle, runtime: &BackendRuntime) -> Option<Command> {
    #[cfg(debug_assertions)]
    {
        let _ = app;
        let _ = runtime;
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
        let sidecar_dir = bundled_backend_dir(app)?;

        #[cfg(target_os = "windows")]
        let sidecar_exe = sidecar_dir.join(BACKEND_PROCESS_NAME);
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
        let port = api_addr(&runtime.origin)?.port().to_string();
        command.arg("--host").arg(LOOPBACK_HOST);
        command.arg("--port").arg(port);
        if let Some(token) = &runtime.token {
            command.arg("--auth-token").arg(token);
        }
        Some(command)
    }
}

#[cfg(not(debug_assertions))]
fn bundled_backend_dir(app: &AppHandle) -> Option<PathBuf> {
    let resource_dir = app.path().resource_dir().ok()?;
    Some(resource_dir.join("binaries").join("python-backend"))
}

fn spawn_backend_if_needed(app: &AppHandle, runtime: &BackendRuntime) -> Option<Child> {
    if backend_autostart_disabled() {
        return None;
    }

    cleanup_stale_backend_processes(app);

    #[cfg(debug_assertions)]
    if backend_port_is_open(&runtime.origin) {
        if !glimpse_backend_is_running(&runtime) {
            eprintln!(
                "Backend port {} is already occupied by another process; skipping backend autostart.",
                runtime.origin
            );
            return None;
        }
        return None;
    }

    let mut command = build_backend_command(app, runtime)?;

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

#[cfg(target_os = "windows")]
fn run_hidden_command(command: &mut Command) {
    let _ = command.creation_flags(CREATE_NO_WINDOW).status();
}

#[cfg(not(target_os = "windows"))]
fn run_hidden_command(command: &mut Command) {
    let _ = command.status();
}

#[cfg(target_os = "windows")]
fn kill_process_tree(pid: u32) {
    let mut command = Command::new("taskkill.exe");
    command.arg("/PID").arg(pid.to_string()).arg("/T").arg("/F");
    run_hidden_command(&mut command);
}

#[cfg(not(target_os = "windows"))]
fn kill_process_tree(_pid: u32) {}

fn stop_tracked_backend_process(child: &mut Child) {
    #[cfg(target_os = "windows")]
    kill_process_tree(child.id());

    let _ = child.kill();
    let _ = child.wait();
}

#[cfg(all(target_os = "windows", not(debug_assertions)))]
fn cleanup_backend_processes_in_dir(sidecar_dir: &Path) {
    let script = r#"
$backendDir = [System.IO.Path]::GetFullPath($args[0])
Get-CimInstance Win32_Process -Filter "Name = 'python-backend.exe'" |
  Where-Object {
    $_.ExecutablePath -and
    ([System.IO.Path]::GetFullPath($_.ExecutablePath)).StartsWith(
      $backendDir,
      [System.StringComparison]::OrdinalIgnoreCase
    )
  } |
  ForEach-Object {
    try {
      Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
    } catch {}
  }
"#;

    let mut command = Command::new("powershell.exe");
    command
        .arg("-NoProfile")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-Command")
        .arg(script)
        .arg(sidecar_dir.as_os_str());
    run_hidden_command(&mut command);
}

#[cfg(all(not(target_os = "windows"), not(debug_assertions)))]
fn cleanup_backend_processes_in_dir(_sidecar_dir: &Path) {}

#[cfg(not(debug_assertions))]
fn cleanup_stale_backend_processes(app: &AppHandle) {
    if let Some(sidecar_dir) = bundled_backend_dir(app) {
        cleanup_backend_processes_in_dir(&sidecar_dir);
    }
}

#[cfg(debug_assertions)]
fn cleanup_stale_backend_processes(_app: &AppHandle) {}

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

fn stop_backend_process(app: &AppHandle, state: &AppState) {
    if let Ok(mut guard) = state.backend_child.lock() {
        if let Some(mut child) = guard.take() {
            stop_tracked_backend_process(&mut child);
        }
    }
    cleanup_stale_backend_processes(app);
}

fn store_backend_runtime(app: &AppHandle, runtime: BackendRuntime) {
    let state = app.state::<AppState>();
    let guard = state.backend_runtime.lock();
    if let Ok(mut guard) = guard {
        *guard = runtime;
    }
}

fn store_backend_child(app: &AppHandle, child: Child) {
    let state = app.state::<AppState>();
    let guard = state.backend_child.lock();
    if let Ok(mut guard) = guard {
        *guard = Some(child);
    }
}

fn quit_application(app: &AppHandle) {
    let state = app.state::<AppState>();
    state.quitting.store(true, Ordering::SeqCst);
    stop_backend_process(app, &state);
    app.exit(0);
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    quit_application(&app);
}

#[tauri::command]
fn get_backend_runtime(app: AppHandle) -> BackendRuntime {
    let state = app.state::<AppState>();
    state
        .backend_runtime
        .lock()
        .map(|runtime| runtime.clone())
        .unwrap_or_default()
}

#[tauri::command]
fn hide_window(window: tauri::WebviewWindow) -> Result<(), String> {
    window.hide().map_err(|error| error.to_string())
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
            get_backend_runtime,
            hide_window,
            focus_window,
            minimize_window,
            start_drag_window,
            toggle_maximize_window,
            is_window_maximized
        ])
        .setup(|app| {
            let runtime = backend_runtime_for_launch();
            store_backend_runtime(app.handle(), runtime.clone());

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
                .menu(&tray_menu)
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        ..
                    } = event
                    {
                        show_main_window(tray.app_handle());
                    }
                });

            if let Some(icon) = app_icon {
                tray_builder.icon(icon).build(app)?;
            } else if let Some(icon) = app.default_window_icon().cloned() {
                tray_builder.icon(icon).build(app)?;
            } else {
                tray_builder.build(app)?;
            }

            show_main_window(app.handle());

            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn_blocking(move || {
                if let Some(child) = spawn_backend_if_needed(&app_handle, &runtime) {
                    store_backend_child(&app_handle, child);
                    let _ = app_handle.emit("glimpse://backend-spawned", ());
                }
            });

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
