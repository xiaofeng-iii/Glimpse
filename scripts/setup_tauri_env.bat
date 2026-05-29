@echo off
setlocal

set "CARGO_BIN=%USERPROFILE%\.cargo\bin"
if exist "%CARGO_BIN%\cargo.exe" (
  set "PATH=%CARGO_BIN%;%PATH%"
)

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo Visual Studio Installer not found.
  exit /b 1
)

set "VS_INSTALL="
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
  set "VS_INSTALL=%%I"
)

if not defined VS_INSTALL (
  echo No Visual Studio instance with the MSVC C++ toolset was found.
  exit /b 1
)

set "VS_DEV_CMD=%VS_INSTALL%\Common7\Tools\VsDevCmd.bat"
if not exist "%VS_DEV_CMD%" (
  echo VsDevCmd.bat not found: %VS_DEV_CMD%
  exit /b 1
)

endlocal & (
  set "PATH=%USERPROFILE%\.cargo\bin;%PATH%"
  set "VS_INSTALL=%VS_INSTALL%"
  set "VS_DEV_CMD=%VS_DEV_CMD%"
)

call "%VS_DEV_CMD%" -host_arch=x64 -arch=x64 >nul
if errorlevel 1 (
  echo Failed to initialize the Visual Studio developer environment.
  exit /b 1
)
