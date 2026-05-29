@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found in PATH.
  exit /b 1
)

call "%~dp0scripts\setup_tauri_env.bat"
if errorlevel 1 (
  echo Failed to initialize the Rust/MSVC environment for Tauri.
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm not found in PATH.
  exit /b 1
)

echo ========================================
echo   Glimpse Release Build
echo ========================================
echo.

echo [1/2] Building Python backend sidecar...
python scripts\build_backend_sidecar.py
if errorlevel 1 (
  echo Backend sidecar build failed.
  exit /b 1
)

echo.
echo [2/2] Building Tauri NSIS installer...
pushd glimpse-frontend
call npm run tauri:build
if errorlevel 1 (
  popd
  echo Tauri build failed.
  exit /b 1
)
popd

echo.
echo Release build completed.
echo Installer output:
echo   glimpse-frontend\src-tauri\target\release\bundle\nsis\
echo.
