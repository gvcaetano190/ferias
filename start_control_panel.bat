@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv nao encontrada. Execute setup_windows.bat primeiro.
    exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\pythonw.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

start "" "%CD%\%PYTHON_EXE%" "%CD%\desktop_control_panel.py"
exit /b 0
