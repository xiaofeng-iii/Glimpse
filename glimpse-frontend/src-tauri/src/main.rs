// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use futures_util::StreamExt;
use memmap2::Mmap;
use serde::Serialize;
#[cfg(not(debug_assertions))]
use std::fmt::Write as FmtWrite;
use std::fs::OpenOptions;
#[cfg(debug_assertions)]
use std::io::{Read, Write};
use std::net::SocketAddr;
#[cfg(not(debug_assertions))]
use std::net::TcpListener;
#[cfg(debug_assertions)]
use std::net::TcpStream;
use std::path::Path;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Mutex,
};
use std::time::{Duration, Instant};
use tauri::image::Image;
use tauri::menu::MenuBuilder;
use tauri::tray::{MouseButton, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, Url, WindowEvent};
use tauri_plugin_updater::{Update, UpdaterExt};
use tokio::io::AsyncWriteExt;

mod updater_signature;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const DEV_API_ORIGIN: &str = "http://127.0.0.1:8000";
const APP_VERSION_ENV: &str = "GLIMPSE_APP_VERSION";
const STABLE_UPDATE_URL: &str = "https://xiaofeng-iii.github.io/Glimpse/updates/stable.json";
const PREVIEW_UPDATE_URL: &str = "https://xiaofeng-iii.github.io/Glimpse/updates/preview.json";
const UPDATE_CONNECT_TIMEOUT: Duration = Duration::from_secs(10);
const UPDATE_CANDIDATE_TOTAL_TIMEOUT: Duration = Duration::from_secs(15 * 60);
const UPDATE_ALL_CANDIDATES_TIMEOUT: Duration = Duration::from_secs(20 * 60);
const UPDATE_MIRROR_STALL_TIMEOUT: Duration = Duration::from_secs(15);
const UPDATE_MAX_INSTALLER_BYTES: u64 = 512 * 1024 * 1024;
const UPDATE_DOWNLOAD_TEMP_PREFIX: &str = "Glimpse-update-download-";
const UPDATE_DOWNLOAD_UA: &str = "Glimpse-Updater";
const DATA_ROOT_ENV: &str = "GLIMPSE_DATA_ROOT";
const PROJECT_ROOT_ENV: &str = "GLIMPSE_PROJECT_ROOT";
#[cfg(not(debug_assertions))]
const LOOPBACK_HOST: &str = "127.0.0.1";
#[cfg(debug_assertions)]
const BACKEND_IDENTITY_MARKER: &str = "Glimpse API";
#[cfg(not(debug_assertions))]
const BACKEND_BUNDLE_NAME: &str = "GlimpseRuntime";
#[cfg(all(target_os = "windows", not(debug_assertions)))]
const BACKEND_PROCESS_NAME: &str = "GlimpseRuntime.exe";
#[cfg(all(not(target_os = "windows"), not(debug_assertions)))]
const BACKEND_PROCESS_NAME: &str = BACKEND_BUNDLE_NAME;
#[cfg(all(target_os = "windows", not(debug_assertions)))]
const LEGACY_BACKENDS: [(&str, &str); 2] = [
    ("glimpse-backend", "glimpse-backend.exe"),
    ("python-backend", "python-backend.exe"),
];
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;
const APP_ICON_PNG: &[u8] = include_bytes!("../../../assets/icons/glimpse_256.png");

mod diagnostics;

struct AppState {
    backend_child: Mutex<Option<Child>>,
    backend_runtime: Mutex<BackendRuntime>,
    quitting: AtomicBool,
    pending_update: Mutex<Option<(Update, Vec<String>)>>,
    update_installing: AtomicBool,
    update_cancel_requested: AtomicBool,
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
            pending_update: Mutex::new(None),
            update_installing: AtomicBool::new(false),
            update_cancel_requested: AtomicBool::new(false),
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

fn non_empty_env_path(name: &str) -> Option<PathBuf> {
    std::env::var_os(name)
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

fn backend_runtime_root(app: &AppHandle) -> Option<PathBuf> {
    if let Some(root) = non_empty_env_path(PROJECT_ROOT_ENV) {
        return Some(root);
    }

    #[cfg(debug_assertions)]
    {
        let _ = app;
        project_root()
    }

    #[cfg(not(debug_assertions))]
    {
        bundled_backend_dir(app)
    }
}

pub(crate) fn backend_data_root(app: &AppHandle) -> Option<PathBuf> {
    if let Some(root) = non_empty_env_path(DATA_ROOT_ENV) {
        return Some(root);
    }

    #[cfg(not(debug_assertions))]
    if let Some(local_app_data) = non_empty_env_path("LOCALAPPDATA") {
        return Some(local_app_data.join("Glimpse").join("GlimpseData"));
    }

    backend_runtime_root(app).map(|root| root.join("GlimpseData"))
}

fn redirect_command_stdio(command: &mut Command, log_path: &Path) -> std::io::Result<()> {
    if let Some(log_dir) = log_path.parent() {
        std::fs::create_dir_all(log_dir)?;
    }

    let stdout_log = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)?;
    let stderr_log = stdout_log.try_clone()?;

    command.stdout(Stdio::from(stdout_log));
    command.stderr(Stdio::from(stderr_log));
    Ok(())
}

fn redirect_backend_stdio(app: &AppHandle, command: &mut Command) -> std::io::Result<()> {
    let data_root = backend_data_root(app).ok_or_else(|| {
        std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "unable to resolve Glimpse data directory",
        )
    })?;
    let log_path = data_root.join("logs").join("glimpse-sidecar.out.log");
    redirect_command_stdio(command, &log_path)
}

fn build_backend_command(app: &AppHandle, runtime: &BackendRuntime) -> Option<Command> {
    let session_id = app
        .state::<diagnostics::DiagnosticsState>()
        .session_id()
        .to_owned();

    #[cfg(debug_assertions)]
    {
        let _ = runtime;
        let root = project_root()?;
        let python_executable = std::env::var("GLIMPSE_PYTHON")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .unwrap_or_else(|| "python".to_string());
        let mut command = Command::new(python_executable);
        command
            .arg("main_api.py")
            .current_dir(root)
            .env(APP_VERSION_ENV, env!("CARGO_PKG_VERSION"))
            .env(diagnostics::BACKEND_SESSION_ID_ENV, session_id);
        return Some(command);
    }

    #[cfg(not(debug_assertions))]
    {
        let sidecar_dir = bundled_backend_dir(app)?;

        #[cfg(target_os = "windows")]
        let sidecar_exe = sidecar_dir.join(BACKEND_PROCESS_NAME);
        #[cfg(not(target_os = "windows"))]
        let sidecar_exe = sidecar_dir.join(BACKEND_BUNDLE_NAME);

        if !sidecar_exe.exists() {
            eprintln!(
                "Bundled backend sidecar not found: {}",
                sidecar_exe.display()
            );
            return None;
        }

        let mut command = Command::new(sidecar_exe);
        command
            .current_dir(&sidecar_dir)
            .env(APP_VERSION_ENV, env!("CARGO_PKG_VERSION"))
            .env(diagnostics::BACKEND_SESSION_ID_ENV, session_id);
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
    Some(resource_dir.join("binaries").join(BACKEND_BUNDLE_NAME))
}

/// 安装完整性校验：更新中断会留下残缺后端（v0.5.0-beta.2 事故，
/// 见 docs/RELEASE.md）。缺失 exe 或 `_internal` 下的 python3x.dll 时
/// 返回缺失项描述，由调用方广播「安装损坏」并跳过启动。
#[cfg(not(debug_assertions))]
fn backend_bundle_missing_file(app: &AppHandle) -> Option<String> {
    let sidecar_dir = bundled_backend_dir(app)?;
    let sidecar_exe = sidecar_dir.join(BACKEND_PROCESS_NAME);
    if !sidecar_exe.is_file() {
        return Some(sidecar_exe.display().to_string());
    }
    let internal_dir = sidecar_dir.join("_internal");
    let has_python_dll = std::fs::read_dir(&internal_dir)
        .map(|entries| {
            entries.filter_map(Result::ok).any(|entry| {
                let name = entry.file_name();
                let name = name.to_string_lossy();
                name.starts_with("python3") && name.ends_with(".dll")
            })
        })
        .unwrap_or(false);
    if !has_python_dll {
        return Some(internal_dir.display().to_string());
    }
    None
}

fn spawn_backend_if_needed(app: &AppHandle, runtime: &BackendRuntime) -> Option<Child> {
    if backend_autostart_disabled() {
        return None;
    }

    cleanup_stale_backend_processes(app);

    #[cfg(not(debug_assertions))]
    if let Some(missing) = backend_bundle_missing_file(app) {
        eprintln!(
            "Bundled backend is incomplete (missing {}); please reinstall Glimpse.",
            missing
        );
        let _ = app.emit("glimpse://backend-corrupted", ());
        return None;
    }

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

    if let Err(error) = redirect_backend_stdio(app, &mut command) {
        eprintln!("Failed to redirect backend output to the sidecar output log: {error}");
    }

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
fn cleanup_backend_processes_in_dir(sidecar_dir: &Path, process_name: &str) {
    let script = r#"
$backendDir = [System.IO.Path]::GetFullPath($args[0]).TrimEnd('\') + '\'
$processName = $args[1]
Get-CimInstance Win32_Process |
  Where-Object {
    $_.Name -ieq $processName -and
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
        .arg(sidecar_dir.as_os_str())
        .arg(process_name);
    run_hidden_command(&mut command);
}

#[cfg(all(not(target_os = "windows"), not(debug_assertions)))]
fn cleanup_backend_processes_in_dir(_sidecar_dir: &Path, _process_name: &str) {}

#[cfg(not(debug_assertions))]
fn cleanup_stale_backend_processes(app: &AppHandle) {
    if let Some(sidecar_dir) = bundled_backend_dir(app) {
        cleanup_backend_processes_in_dir(&sidecar_dir, BACKEND_PROCESS_NAME);
    }

    #[cfg(target_os = "windows")]
    if let Ok(resource_dir) = app.path().resource_dir() {
        for (bundle_name, process_name) in LEGACY_BACKENDS {
            let legacy_sidecar_dir = resource_dir.join("binaries").join(bundle_name);
            cleanup_backend_processes_in_dir(&legacy_sidecar_dir, process_name);
        }
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

#[derive(Serialize)]
struct AvailableUpdate {
    version: String,
    notes: Option<String>,
}

#[derive(Clone, Serialize)]
struct UpdateDownloadProgress {
    downloaded: u64,
    total: Option<u64>,
}

#[derive(Serialize)]
#[serde(rename_all = "snake_case")]
enum UpdateInstallStatus {
    Installed,
    Cancelled,
}

struct DownloadedInstaller {
    _temp_file: tempfile::NamedTempFile,
    bytes: Mmap,
}

#[derive(Debug)]
enum UpdateDownloadError {
    Cancelled,
    Sources(Vec<String>),
}

impl UpdateDownloadError {
    fn message(&self) -> String {
        match self {
            Self::Cancelled => "update download cancelled".to_string(),
            Self::Sources(errors) if errors.is_empty() => "no download candidates".to_string(),
            Self::Sources(errors) => errors.join("; "),
        }
    }
}

fn parse_mirrors_from_update(update: &Update) -> Vec<String> {
    update
        .raw_json
        .get("mirrors")
        .and_then(|value| value.as_array())
        .map(|array| {
            array
                .iter()
                .filter_map(|item| item.as_str().map(ToString::to_string))
                .collect()
        })
        .unwrap_or_default()
}

fn update_download_candidates(
    original_url: &Url,
    mirror_prefixes: &[String],
    prefer_mirror: bool,
) -> Vec<String> {
    let mut candidates = Vec::new();
    if prefer_mirror {
        for prefix in mirror_prefixes {
            candidates.push(format!("{}{}", prefix, original_url));
        }
    }
    candidates.push(original_url.to_string());
    candidates
}

fn update_installer_file_name(update: &Update) -> Result<&str, String> {
    update
        .download_url
        .path_segments()
        .and_then(|segments| segments.last())
        .filter(|file_name| !file_name.is_empty())
        .ok_or_else(|| {
            format!(
                "update download URL has no installer file name: {}",
                update.download_url
            )
        })
}

fn emit_update_progress(app: &AppHandle, progress: &UpdateDownloadProgress) {
    if app
        .emit("glimpse://update-download-progress", progress)
        .is_err()
    {
        eprintln!("Failed to emit update download progress");
    }
}

fn update_download_cancelled(cancel_requested: &AtomicBool) -> bool {
    cancel_requested.load(Ordering::SeqCst)
}

async fn download_from_candidate(
    client: &reqwest::Client,
    url: &str,
    app: &AppHandle,
    cancel_requested: &AtomicBool,
) -> Result<DownloadedInstaller, UpdateDownloadError> {
    if update_download_cancelled(cancel_requested) {
        return Err(UpdateDownloadError::Cancelled);
    }

    let response = client
        .get(url)
        .header(reqwest::header::USER_AGENT, UPDATE_DOWNLOAD_UA)
        .send()
        .await
        .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;

    if !response.status().is_success() {
        return Err(UpdateDownloadError::Sources(vec![format!(
            "HTTP {}",
            response.status()
        )]));
    }

    if let Some(content_type) = response.headers().get(reqwest::header::CONTENT_TYPE) {
        if let Ok(value) = content_type.to_str() {
            if value.contains("text/html") {
                return Err(UpdateDownloadError::Sources(vec![
                    "mirror returned HTML page".to_string(),
                ]));
            }
        }
    }

    let total = response.content_length();
    if total.is_some_and(|length| length > UPDATE_MAX_INSTALLER_BYTES) {
        return Err(UpdateDownloadError::Sources(vec![format!(
            "installer is larger than {} bytes",
            UPDATE_MAX_INSTALLER_BYTES
        )]));
    }

    let temp_file = tempfile::Builder::new()
        .prefix(UPDATE_DOWNLOAD_TEMP_PREFIX)
        .suffix(".installer")
        .tempfile()
        .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;
    let mut writer = tokio::fs::File::from_std(
        temp_file
            .reopen()
            .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?,
    );

    let mut stream = response.bytes_stream();
    let mut downloaded: u64 = 0;
    let mut sniffed = false;
    let mut last_percent = 0;
    let mut last_mib = 0;
    emit_update_progress(app, &UpdateDownloadProgress { downloaded, total });

    loop {
        if update_download_cancelled(cancel_requested) {
            return Err(UpdateDownloadError::Cancelled);
        }

        let chunk_result = tokio::time::timeout(UPDATE_MIRROR_STALL_TIMEOUT, stream.next())
            .await
            .map_err(|_| UpdateDownloadError::Sources(vec!["download stalled".to_string()]))?;
        let Some(chunk) = chunk_result else {
            break;
        };
        let chunk = chunk.map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;

        if !sniffed {
            if chunk.starts_with(b"<") {
                return Err(UpdateDownloadError::Sources(vec![
                    "mirror returned HTML content".to_string(),
                ]));
            }
            sniffed = true;
        }

        downloaded = downloaded.checked_add(chunk.len() as u64).ok_or_else(|| {
            UpdateDownloadError::Sources(vec!["installer size overflow".to_string()])
        })?;
        if downloaded > UPDATE_MAX_INSTALLER_BYTES {
            return Err(UpdateDownloadError::Sources(vec![format!(
                "installer is larger than {} bytes",
                UPDATE_MAX_INSTALLER_BYTES
            )]));
        }

        writer
            .write_all(&chunk)
            .await
            .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;

        let progress = UpdateDownloadProgress { downloaded, total };
        let should_emit = match total {
            Some(total) if total > 0 => {
                let percent = (downloaded * 100 / total).min(100);
                if percent > last_percent {
                    last_percent = percent;
                    true
                } else {
                    false
                }
            }
            _ => {
                let mib = downloaded / (1024 * 1024);
                if mib > last_mib {
                    last_mib = mib;
                    true
                } else {
                    false
                }
            }
        };
        if should_emit {
            emit_update_progress(app, &progress);
        }
    }

    writer
        .sync_all()
        .await
        .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;
    drop(writer);

    let bytes = unsafe { Mmap::map(temp_file.as_file()) }
        .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;
    emit_update_progress(
        app,
        &UpdateDownloadProgress {
            downloaded,
            total: Some(downloaded),
        },
    );

    Ok(DownloadedInstaller {
        _temp_file: temp_file,
        bytes,
    })
}

async fn download_update_with_mirrors(
    app: &AppHandle,
    original_url: &Url,
    signature: &str,
    announced_version: &str,
    expected_file_name: &str,
    mirror_prefixes: &[String],
    prefer_mirror: bool,
    cancel_requested: &AtomicBool,
) -> Result<DownloadedInstaller, UpdateDownloadError> {
    let client = reqwest::Client::builder()
        .connect_timeout(UPDATE_CONNECT_TIMEOUT)
        .timeout(UPDATE_CANDIDATE_TOTAL_TIMEOUT)
        .build()
        .map_err(|error| UpdateDownloadError::Sources(vec![error.to_string()]))?;
    let candidates = update_download_candidates(original_url, mirror_prefixes, prefer_mirror);
    let deadline = Instant::now() + UPDATE_ALL_CANDIDATES_TIMEOUT;

    // 下载失败与签名失败都只淘汰当前候选源；全部失败时汇总每个源的报错，
    // 避免只把最后的直连错误暴露给前端，掩盖镜像是否被尝试过。
    let mut errors = Vec::new();
    for candidate in candidates {
        if update_download_cancelled(cancel_requested) {
            return Err(UpdateDownloadError::Cancelled);
        }
        if Instant::now() >= deadline {
            errors.push("all update sources exceeded the total download timeout".to_string());
            return Err(UpdateDownloadError::Sources(errors));
        }

        let installer =
            match download_from_candidate(&client, &candidate, app, cancel_requested).await {
                Ok(installer) => installer,
                Err(UpdateDownloadError::Cancelled) => {
                    return Err(UpdateDownloadError::Cancelled);
                }
                Err(UpdateDownloadError::Sources(source_errors)) => {
                    for error in source_errors {
                        errors.push(format!("{}: {}", candidate, error));
                    }
                    continue;
                }
            };

        if let Err(error) = updater_signature::verify_update_signature(
            &installer.bytes,
            signature,
            announced_version,
            expected_file_name,
        ) {
            errors.push(format!(
                "{}: signature verification failed: {}",
                candidate, error
            ));
            continue;
        }
        return Ok(installer);
    }

    Err(UpdateDownloadError::Sources(errors))
}

struct UpdateInstallGuard<'a> {
    installing: &'a AtomicBool,
    cancel_requested: &'a AtomicBool,
}

impl Drop for UpdateInstallGuard<'_> {
    fn drop(&mut self) {
        self.cancel_requested.store(false, Ordering::SeqCst);
        self.installing.store(false, Ordering::SeqCst);
    }
}

#[tauri::command]
async fn cancel_update_download(app: AppHandle) -> Result<(), String> {
    let state = app.state::<AppState>();
    if state.update_installing.load(Ordering::SeqCst) {
        state.update_cancel_requested.store(true, Ordering::SeqCst);
    }
    Ok(())
}

#[tauri::command]
async fn check_for_update(
    app: AppHandle,
    channel: String,
) -> Result<Option<AvailableUpdate>, String> {
    let state = app.state::<AppState>();
    if state.update_installing.load(Ordering::SeqCst) {
        return Err("An update installation is already in progress".to_string());
    }

    let endpoint = match channel.as_str() {
        "stable" => STABLE_UPDATE_URL,
        "preview" => PREVIEW_UPDATE_URL,
        _ => return Err("Unknown update channel".to_string()),
    };
    let url = Url::parse(endpoint).map_err(|error| error.to_string())?;
    let updater = app
        .updater_builder()
        .endpoints(vec![url])
        .map_err(|error| error.to_string())?
        .on_before_exit({
            let app = app.clone();
            move || {
                let state = app.state::<AppState>();
                state.quitting.store(true, Ordering::SeqCst);
                stop_backend_process(&app, &state);
            }
        })
        .build()
        .map_err(|error| error.to_string())?;
    let update = updater.check().await.map_err(|error| error.to_string())?;
    let available = update.as_ref().map(|update| AvailableUpdate {
        version: update.version.clone(),
        notes: update.body.clone(),
    });
    let state = app.state::<AppState>();
    let mirrors = update
        .as_ref()
        .map(parse_mirrors_from_update)
        .unwrap_or_default();
    *state
        .pending_update
        .lock()
        .map_err(|error| error.to_string())? = update.map(|u| (u, mirrors));
    Ok(available)
}

#[tauri::command]
async fn install_checked_update(
    app: AppHandle,
    prefer_mirror: bool,
) -> Result<UpdateInstallStatus, String> {
    let state = app.state::<AppState>();
    if state
        .update_installing
        .compare_exchange(false, true, Ordering::SeqCst, Ordering::SeqCst)
        .is_err()
    {
        return Err("An update installation is already in progress".to_string());
    }
    let _install_guard = UpdateInstallGuard {
        installing: &state.update_installing,
        cancel_requested: &state.update_cancel_requested,
    };

    let (update, mirrors) = state
        .pending_update
        .lock()
        .map_err(|error| error.to_string())?
        .as_ref()
        .cloned()
        .ok_or("No checked update available")?;
    let expected_file_name = update_installer_file_name(&update)?.to_owned();

    let installer = match download_update_with_mirrors(
        &app,
        &update.download_url,
        &update.signature,
        &update.version,
        &expected_file_name,
        &mirrors,
        prefer_mirror,
        &state.update_cancel_requested,
    )
    .await
    {
        Ok(installer) => installer,
        Err(UpdateDownloadError::Cancelled) => return Ok(UpdateInstallStatus::Cancelled),
        Err(error) => return Err(error.message()),
    };

    if update_download_cancelled(&state.update_cancel_requested) {
        return Ok(UpdateInstallStatus::Cancelled);
    }

    update
        .install(&installer.bytes)
        .map_err(|error| error.to_string())?;
    Ok(UpdateInstallStatus::Installed)
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

/// 单张复制与整组同逻辑（CF_HDROP 文件列表，单元素）：
/// 微信/资源管理器粘贴时直接得到图片本身，且天然支持异步线程不卡 UI。
#[tauri::command]
async fn copy_image_file_to_clipboard(app: tauri::AppHandle, path: String) -> Result<(), String> {
    copy_image_files_to_clipboard(app, vec![path]).await
}

/// 把整组图片以文件列表（CF_HDROP）形式写入剪贴板，粘贴到资源管理器/聊天工具
/// 即可得到独立图片文件。路径为相对后端数据根目录的相对路径，与 /api/images
/// 的解析规则一致（canonicalize 后必须仍位于数据根目录内）。
#[tauri::command]
async fn copy_image_files_to_clipboard(
    app: tauri::AppHandle,
    paths: Vec<String>,
) -> Result<(), String> {
    #[cfg(windows)]
    {
        use clipboard_win::Clipboard;

        let data_root = backend_data_root(&app).ok_or("backend data root unavailable")?;
        let root_canonical = data_root
            .canonicalize()
            .map_err(|error| format!("resolve data root: {error}"))?;

        let mut files = Vec::with_capacity(paths.len());
        for relative in &paths {
            let resolved = data_root
                .join(relative)
                .canonicalize()
                .map_err(|error| format!("resolve image {relative}: {error}"))?;
            if !resolved.starts_with(&root_canonical) {
                return Err(format!("image path escapes data root: {relative}"));
            }
            if !resolved.is_file() {
                return Err(format!("image file not found: {relative}"));
            }
            files.push(
                resolved
                    .to_string_lossy()
                    .trim_start_matches(r"\\?\")
                    .to_string(),
            );
        }

        let clipboard =
            Clipboard::new_attempts(10).map_err(|error| format!("open clipboard: {error:?}"))?;
        let _clipboard = &clipboard;
        clipboard_win::raw::set_file_list(&files)
            .map_err(|error| format!("set file list: {error:?}"))?;
        Ok(())
    }

    #[cfg(not(windows))]
    {
        let _ = (app, paths);
        Err("file list clipboard is only supported on Windows".to_string())
    }
}

fn load_app_icon() -> Option<Image<'static>> {
    Image::from_bytes(APP_ICON_PNG).ok().map(Image::to_owned)
}

/// 引擎级关闭 WebView2 默认 UI：桌面应用不暴露浏览器右键菜单（图二）与
/// 权限/脚本类原生弹窗，右键与提醒交互全部由前端自建菜单与 toast 负责。
/// 引擎开关是兜底，前端另有应用层拦截。
#[cfg(windows)]
fn harden_webview2_default_ui(window: &tauri::WebviewWindow) {
    use webview2_com::Microsoft::Web::WebView2::Win32::{
        ICoreWebView2, ICoreWebView2PermissionRequestedEventArgs,
        COREWEBVIEW2_PERMISSION_STATE_DENY,
    };
    use webview2_com::PermissionRequestedEventHandler;

    let result = window.with_webview(|webview| {
        // SAFETY: COM 调用在 with_webview 派发的 UI 线程上执行，接口指针由控制器持有。
        let outcome = unsafe {
            (|| -> Result<(), String> {
                let core = webview
                    .controller()
                    .CoreWebView2()
                    .map_err(|error| format!("core webview: {error:?}"))?;

                let settings = core
                    .Settings()
                    .map_err(|error| format!("settings: {error:?}"))?;
                settings
                    .SetAreDefaultContextMenusEnabled(false)
                    .map_err(|error| format!("disable context menus: {error:?}"))?;
                settings
                    .SetAreDefaultScriptDialogsEnabled(false)
                    .map_err(|error| format!("disable script dialogs: {error:?}"))?;

                // 权限请求一律静默拒绝：未来任何代码触发权限（剪贴板/麦克风/定位…）
                // 都不会弹出 WebView2 原生询问，最坏结果是该功能静默不工作。
                let handler = PermissionRequestedEventHandler::create(Box::new(
                    |_core: Option<ICoreWebView2>,
                     args: Option<ICoreWebView2PermissionRequestedEventArgs>| {
                        let args = args.ok_or_else(|| {
                            windows::core::Error::from_hresult(windows::core::HRESULT(
                                0x8000_4005u32 as i32,
                            ))
                        })?;
                        args.SetState(COREWEBVIEW2_PERMISSION_STATE_DENY)?;
                        Ok(())
                    },
                ));
                let mut token = 0i64;
                core.add_PermissionRequested(&handler, &mut token)
                    .map_err(|error| format!("register permission handler: {error:?}"))?;

                Ok(())
            })()
        };

        if let Err(error) = outcome {
            eprintln!("Failed to harden WebView2 default UI: {error}");
        }
    });

    if let Err(error) = result {
        eprintln!("Failed to access platform webview: {error}");
    }
}

fn cleanup_stale_update_downloads() {
    let Ok(entries) = std::fs::read_dir(std::env::temp_dir()) else {
        return;
    };
    for entry in entries.flatten() {
        let Some(file_name) = entry.file_name().to_str().map(ToString::to_string) else {
            continue;
        };
        if !file_name.starts_with(UPDATE_DOWNLOAD_TEMP_PREFIX) {
            continue;
        }
        if let Ok(file_type) = entry.file_type() {
            if file_type.is_file() {
                if let Err(error) = std::fs::remove_file(entry.path()) {
                    eprintln!(
                        "Failed to clean stale update download {}: {error}",
                        entry.path().display()
                    );
                }
            }
        }
    }
}

fn main() {
    cleanup_stale_update_downloads();
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(AppState::default())
        .manage(diagnostics::DiagnosticsState::default())
        .invoke_handler(tauri::generate_handler![
            check_for_update,
            install_checked_update,
            cancel_update_download,
            quit_app,
            get_backend_runtime,
            hide_window,
            focus_window,
            minimize_window,
            start_drag_window,
            toggle_maximize_window,
            is_window_maximized,
            copy_image_files_to_clipboard,
            copy_image_file_to_clipboard,
            diagnostics::append_diagnostic_logs,
            diagnostics::diagnostic_session_id,
            diagnostics::open_logs_directory,
            diagnostics::export_diagnostics
        ])
        .setup(|app| {
            let runtime = backend_runtime_for_launch();
            store_backend_runtime(app.handle(), runtime.clone());

            if let Some(window) = app.get_webview_window("main") {
                #[cfg(windows)]
                harden_webview2_default_ui(&window);
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

#[cfg(test)]
mod tests {
    use super::redirect_command_stdio;
    use super::{update_download_candidates, UpdateDownloadError};
    use std::path::Path;
    use std::process::Command;
    use tauri::Url;

    fn output_command(label: &str) -> Command {
        #[cfg(target_os = "windows")]
        {
            let mut command = Command::new("cmd.exe");
            command.args([
                "/C",
                &format!("echo stdout-{label} & echo stderr-{label} 1>&2"),
            ]);
            command
        }

        #[cfg(not(target_os = "windows"))]
        {
            let mut command = Command::new("sh");
            command.args([
                "-c",
                &format!("echo stdout-{label}; echo stderr-{label} >&2"),
            ]);
            command
        }
    }

    fn run_redirected_probe(log_path: &Path, label: &str) {
        let mut command = output_command(label);
        redirect_command_stdio(&mut command, log_path).expect("redirect probe output");
        let status = command.status().expect("run redirected probe");
        assert!(status.success());
    }

    #[test]
    fn update_download_candidates_prefer_mirrors_then_direct() {
        let url = Url::parse("https://github.com/example/Glimpse_0.5.0_x64-setup.exe").unwrap();
        let mirrors = vec![
            "https://mirror-1.example/".to_owned(),
            "https://mirror-2.example/".to_owned(),
        ];

        assert_eq!(
            update_download_candidates(&url, &mirrors, true),
            vec![
                "https://mirror-1.example/https://github.com/example/Glimpse_0.5.0_x64-setup.exe"
                    .to_owned(),
                "https://mirror-2.example/https://github.com/example/Glimpse_0.5.0_x64-setup.exe"
                    .to_owned(),
                "https://github.com/example/Glimpse_0.5.0_x64-setup.exe".to_owned(),
            ]
        );
        assert_eq!(
            update_download_candidates(&url, &mirrors, false),
            vec!["https://github.com/example/Glimpse_0.5.0_x64-setup.exe".to_owned()]
        );
    }

    #[test]
    fn update_download_error_reports_every_source() {
        let error = UpdateDownloadError::Sources(vec![
            "mirror-a: HTTP 429".to_owned(),
            "direct: connection closed".to_owned(),
        ]);
        assert_eq!(
            error.message(),
            "mirror-a: HTTP 429; direct: connection closed"
        );
        assert_eq!(
            UpdateDownloadError::Sources(Vec::new()).message(),
            "no download candidates"
        );
    }

    #[test]
    fn sidecar_output_redirection_captures_both_streams_and_appends() {
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .expect("system clock after epoch")
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!(
            "glimpse-sidecar-log-test-{}-{unique}",
            std::process::id()
        ));
        let log_path = temp_dir.join("logs").join("glimpse-sidecar.out.log");

        run_redirected_probe(&log_path, "first");
        run_redirected_probe(&log_path, "second");

        let output = std::fs::read_to_string(&log_path).expect("read sidecar output log");
        for expected in [
            "stdout-first",
            "stderr-first",
            "stdout-second",
            "stderr-second",
        ] {
            assert!(output.contains(expected), "missing {expected}: {output}");
        }

        std::fs::remove_dir_all(temp_dir).expect("remove sidecar log test directory");
    }
}
