@echo off
echo Iniciando compilacao do Painel de Controle de Ferias...

:: Verifica se a pasta assets existe
if not exist assets\icon.ico (
    echo ERRO: Arquivo assets\icon.ico nao encontrado!
    pause
    exit /b 1
)

:: Executa o PyInstaller com configuracoes otimizadas
.venv\Scripts\pyinstaller.exe ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --icon "assets\icon.ico" ^
    --name "ControleFeriasPanel" ^
    --add-data "assets\icon.ico;assets" ^
    desktop_control_panel.py

echo.
echo Compilacao concluida com sucesso!
echo O executavel esta dentro da pasta dist\
pause
