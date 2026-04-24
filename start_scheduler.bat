@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Rode setup_windows.bat primeiro.
  exit /b 1
)

call .venv\Scripts\activate.bat
python run_scheduler.py
