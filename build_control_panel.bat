@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv nao encontrada. Execute setup_windows.bat primeiro.
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install pyinstaller >nul
python -m PyInstaller --noconfirm "ControleFeriasPanel.spec"

echo Build concluido em "%CD%\dist\ControleFeriasPanel"
exit /b 0
