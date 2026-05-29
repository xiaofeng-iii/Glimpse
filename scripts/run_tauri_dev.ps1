$ErrorActionPreference = 'Stop'

$root = (Split-Path -Parent $PSScriptRoot)
$healthUrl = 'http://127.0.0.1:8000/api/health'
$logsDir = Join-Path $root '.logs'
$backendLog = Join-Path $logsDir 'backend-dev.log'
$tauriLog = Join-Path $logsDir 'tauri-dev.log'

function Test-GlimpseBackendHealth {
  try {
    $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
    return $response.status -eq 'healthy'
  } catch {
    return $false
  }
}

$pythonCommand = Get-Command python -ErrorAction Stop
$pythonExe = $pythonCommand.Source

$env:GLIMPSE_PYTHON = $pythonExe
$env:GLIMPSE_SKIP_BACKEND_AUTOSTART = '1'

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if (-not (Test-GlimpseBackendHealth)) {
  $backendCommand = "cd /d `"$root`" && `"$pythonExe`" main_api.py > `"$backendLog`" 2>&1"
  Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList "/c", $backendCommand | Out-Null

  $backendReady = $false
  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (Test-GlimpseBackendHealth) {
      $backendReady = $true
      break
    }
  }

  if (-not $backendReady) {
    Add-Content -Path $backendLog -Value "`n[run_tauri_dev.ps1] Backend health check timed out at $(Get-Date -Format o)"
  }
}

$command = "cd /d `"$root`" && call scripts\setup_tauri_env.bat && cd /d `"$root\glimpse-frontend`" && npm run tauri:dev > `"$tauriLog`" 2>&1"

Start-Process -WindowStyle Hidden -FilePath "cmd.exe" -ArgumentList "/c", $command | Out-Null
