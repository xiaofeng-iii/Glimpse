@echo off
setlocal

cd /d "%~dp0"

call scripts\setup_tauri_env.bat
if errorlevel 1 (
  echo Failed to initialize the Rust/MSVC environment for Tauri.
  exit /b 1
)

cd /d "%~dp0glimpse-frontend"
npm.cmd run tauri:dev -- --config tauri.dev.conf.json
