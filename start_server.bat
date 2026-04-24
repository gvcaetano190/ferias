@echo off
setlocal

cd /d %~dp0

if not exist ".venv\Scripts\python.exe" (
    echo .venv nao encontrada. Execute setup_windows.bat primeiro.
    exit /b 1
)

if /I not "%START_SCHEDULER_WITH_SERVER%"=="0" (
    start "django_app_scheduler" cmd /c "%~dp0start_scheduler.bat"
)

call .venv\Scripts\activate.bat
python run_server.py
