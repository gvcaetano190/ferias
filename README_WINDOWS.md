# Windows

## Pré-requisitos

- Python 3.11
- Git
- PowerShell do Windows
- Módulo Active Directory na máquina/servidor que for executar bloqueio real

## Setup inicial

Na pasta do projeto:

```bat
setup_windows.bat
```

Esse script:

- cria `.venv` se necessário
- instala dependências
- roda `migrate`
- roda `collectstatic`

## Subir o projeto

Opção simples:

```bat
start_server.bat
```

Opção manual:

```bat
.venv\Scripts\activate
python run_server.py
```

## Fluxo manual completo

```bat
py -3.11 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python run_server.py
```

## Observações

- O projeto usa Waitress + WhiteNoise para servir a aplicação e os arquivos estáticos sem depender de Docker.
- Em máquina sem acesso ao AD, a interface do módulo `block` funciona, mas bloqueio/desbloqueio real pode falhar.
- O executor AD prioriza `powershell` no Windows e usa `-ExecutionPolicy Bypass`.
- Se a policy do PowerShell bloquear ativação manual da `.venv`, prefira usar os arquivos `.bat`.
- Se a porta `8000` estiver ocupada, rode com variáveis de ambiente:

```bat
set DJANGO_PORT=8010
python run_server.py
```
