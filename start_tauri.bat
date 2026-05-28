@echo off
where cargo >nul 2>nul
if errorlevel 1 (
  echo Rust toolchain not found. Please install Rust from https://rustup.rs/
  pause
  exit /b 1
)

echo ========================================
echo   Glimpse Tauri Popup Dev
echo ========================================
echo.

echo [1] Starting Python API Server...
start "Glimpse API" cmd /k "cd /d %~dp0 && python main_api.py"

echo Waiting for API server to start...
timeout /t 5 /nobreak > nul

echo [2] Starting Tauri desktop shell...
start "Glimpse Tauri" cmd /k "cd /d %~dp0glimpse-frontend && npm run tauri:dev"

echo.
echo ========================================
echo   Desktop popup flow started
echo   API: http://localhost:8000
echo   Desktop shell: Tauri window
echo ========================================
echo.
pause
