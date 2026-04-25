@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv nao encontrada. Execute setup_windows.bat primeiro.
    exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\python.exe"
if exist ".venv\Scripts\pythonw.exe" (
    set "PYTHON_EXE=.venv\Scripts\pythonw.exe"
)

set "AUTO_START_SCHEDULER=0"
for /f %%i in ('".venv\Scripts\python.exe" "%~dp0check_scheduler_autostart.py"') do set "AUTO_START_SCHEDULER=%%i"

if /I "%AUTO_START_SCHEDULER%"=="1" (
    call "%~dp0start_scheduler.bat"
)

powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command ^
  "Start-Process -FilePath '%CD%\%PYTHON_EXE%' -ArgumentList 'run_server.py' -WorkingDirectory '%CD%' -WindowStyle Hidden"

exit /b 0
