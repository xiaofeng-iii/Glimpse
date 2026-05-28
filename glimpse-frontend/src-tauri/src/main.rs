// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;
use tauri::Manager;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

const API_HOST: &str = "127.0.0.1:8000";
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

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

fn spawn_backend_if_needed() {
    if backend_is_running() {
        return;
    }

    let Some(root) = project_root() else {
        eprintln!("Could not resolve project root for Python backend startup");
        return;
    };

    let mut command = Command::new("python");
    command.arg("main_api.py").current_dir(root);

    #[cfg(target_os = "windows")]
    {
        command.creation_flags(CREATE_NO_WINDOW);
    }

    if let Err(error) = command.spawn() {
        eprintln!("Failed to spawn Python backend automatically: {error}");
    }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(debug_assertions)]
            spawn_backend_if_needed();

            let window = app
                .get_webview_window("main")
                .expect("main window should exist");
            let _ = window.set_focus();

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
