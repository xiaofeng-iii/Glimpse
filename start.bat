@echo off
echo ========================================
echo   Glimpse Quick Start
echo ========================================
echo.

echo [1] Starting Python API Server...
start "Glimpse API" cmd /k "cd /d %~dp0 && python main_api.py"

echo Waiting for API server to start...
timeout /t 5 /nobreak > nul

echo [2] Starting Frontend Dev Server...
start "Glimpse Frontend" cmd /k "cd /d %~dp0glimpse-frontend && npm run dev"

echo.
echo ========================================
echo   Servers started!
echo   API: http://localhost:8000
echo   Frontend: http://localhost:1420
echo ========================================
echo.
pause