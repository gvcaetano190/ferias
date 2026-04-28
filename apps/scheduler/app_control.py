from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagedProcess:
    pid: int
    command_line: str


@dataclass(frozen=True)
class ApplicationStatus:
    web_running: bool
    qcluster_running: bool
    web_processes: tuple[ManagedProcess, ...]
    qcluster_processes: tuple[ManagedProcess, ...]
    url: str

    @property
    def overall_label(self) -> str:
        if self.web_running and self.qcluster_running:
            return "Rodando"
        if self.web_running or self.qcluster_running:
            return "Parcial"
        return "Parado"


class ApplicationControlService:
    def __init__(self, project_root: Path | None = None) -> None:
        import sys

        if getattr(sys, "frozen", False):
            exe_path = Path(sys.executable).resolve()
            if exe_path.parent.name == "dist":
                self.project_root = exe_path.parents[1]
            else:
                self.project_root = exe_path.parent
        else:
            self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.python_exe = self._resolve_python()
        self.pythonw_exe = self._resolve_python(gui=True)
        self.host = os.environ.get("DJANGO_HOST", "127.0.0.1")
        self.port = int(os.environ.get("DJANGO_PORT", "8000"))
        self.url = f"http://{self.host}:{self.port}"
        self.last_port_conflict: ManagedProcess | None = None

    def status_snapshot(self) -> ApplicationStatus:
        processes = self._list_managed_processes()
        web_processes = tuple(processes["web"])
        qcluster_processes = tuple(processes["qcluster"])
        return ApplicationStatus(
            web_running=bool(web_processes),
            qcluster_running=bool(qcluster_processes),
            web_processes=web_processes,
            qcluster_processes=qcluster_processes,
            url=self.url,
        )

    def start_system(self) -> tuple[bool, str]:
        if platform.system().lower() != "windows":
            return False, "O painel desktop foi preparado para Windows."

        self.last_port_conflict = None
        actions = []
        status = self.status_snapshot()

        if not (self.project_root / "run_server.py").exists() or not (self.project_root / "manage.py").exists():
            return False, f"ERRO: Arquivos do sistema não encontrados na pasta {self.project_root}."

        if not status.web_running:
            if self._is_port_in_use():
                self.last_port_conflict = self._find_process_on_port(self.port)
                return False, self._build_port_in_use_message()
            self._spawn_hidden(["run_server.py"])
            actions.append("aplicação web")

        if not status.qcluster_running:
            self._spawn_hidden(["manage.py", "qcluster"])
            actions.append("worker Q2")

        if not actions:
            return True, "Sistema já estava rodando."

        time.sleep(2)
        return True, "Iniciado: " + ", ".join(actions) + "."

    def stop_system(self) -> tuple[bool, str]:
        self.last_port_conflict = None
        status = self.status_snapshot()
        stopped = 0
        for process in [*status.web_processes, *status.qcluster_processes]:
            self._kill_pid(process.pid)
            stopped += 1
        if not stopped:
            return True, "Sistema já estava parado."
        return True, f"Sistema pausado. Processos encerrados: {stopped}."

    def restart_system(self) -> tuple[bool, str]:
        ok, stop_message = self.stop_system()
        if not ok:
            return False, stop_message
        time.sleep(2)
        ok, start_message = self.start_system()
        if not ok:
            return False, start_message
        return True, f"{stop_message} {start_message}"

    def restart_web_application(self) -> tuple[bool, str]:
        if platform.system().lower() != "windows":
            return False, "O reinício automático da aplicação foi preparado apenas para Windows."
        status = self.status_snapshot()
        for process in status.web_processes:
            self._kill_pid(process.pid)
        time.sleep(2)
        self._spawn_hidden(["run_server.py"])
        return True, "Reinício da aplicação web solicitado. A conexão pode cair por alguns segundos."

    def stop_port_conflict(self) -> tuple[bool, str]:
        conflict = self.last_port_conflict or self._find_process_on_port(self.port)
        if not conflict:
            self.last_port_conflict = None
            return True, f"Nenhum processo foi encontrado usando a porta {self.port}."

        self._kill_pid(conflict.pid)
        time.sleep(2)
        if self._is_port_in_use():
            remaining = self._find_process_on_port(self.port)
            self.last_port_conflict = remaining
            if remaining:
                return (
                    False,
                    f"Não foi possível liberar a porta {self.port}. "
                    f"Ela continua em uso pelo PID {remaining.pid}.",
                )
            return False, f"Não foi possível liberar a porta {self.port}."

        self.last_port_conflict = None
        return True, f"Processo {conflict.pid} encerrado e porta {self.port} liberada."

    def open_system(self) -> None:
        webbrowser.open(self.url)

    def open_admin(self) -> None:
        webbrowser.open(f"{self.url}/admin/")

    def _resolve_python(self, *, gui: bool = False) -> Path:
        script_name = "pythonw.exe" if gui else "python.exe"
        preferred = self.project_root / ".venv" / "Scripts" / script_name
        if preferred.exists():
            return preferred
        fallback = self.project_root / ".venv" / "Scripts" / "python.exe"
        return fallback

    def _spawn_hidden(self, args: list[str]) -> None:
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        executable = self.pythonw_exe if self.pythonw_exe.exists() else self.python_exe
        subprocess.Popen(
            [str(executable), *args],
            cwd=str(self.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )

    def _kill_pid(self, pid: int) -> None:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=creationflags,
        )

    def _is_port_in_use(self) -> bool:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            return sock.connect_ex((self.host, self.port)) == 0

    def _build_port_in_use_message(self) -> str:
        if not self.last_port_conflict:
            return f"ERRO: A porta {self.port} já está sendo usada por outro programa."
        command = self.last_port_conflict.command_line or "(sem linha de comando)"
        return (
            f"ERRO: A porta {self.port} já está sendo usada por outro programa. "
            f"PID: {self.last_port_conflict.pid}. Comando: {command}"
        )

    def _find_process_on_port(self, port: int) -> ManagedProcess | None:
        if platform.system().lower() != "windows":
            return None

        command = (
            f"$connection = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | "
            "Select-Object -First 1; "
            "if (-not $connection) { return }; "
            "$process = Get-CimInstance Win32_Process -Filter \"ProcessId = $($connection.OwningProcess)\"; "
            "if (-not $process) { return }; "
            "$process | Select-Object ProcessId, CommandLine | ConvertTo-Json -Compress"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            check=False,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return None
        payload = (result.stdout or "").strip()
        if not payload:
            return None
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        pid = int(data.get("ProcessId") or 0)
        if not pid:
            return None
        return ManagedProcess(
            pid=pid,
            command_line=str(data.get("CommandLine") or ""),
        )

    def _list_managed_processes(self) -> dict[str, list[ManagedProcess]]:
        processes = self._query_python_processes()
        web_processes: list[ManagedProcess] = []
        qcluster_processes: list[ManagedProcess] = []
        process_index: dict[int, dict] = {}
        for item in processes:
            pid = int(item.get("ProcessId") or 0)
            if pid:
                process_index[pid] = item
        for item in processes:
            command_line = str(item.get("CommandLine") or "")
            pid = int(item.get("ProcessId") or 0)
            if not pid or not command_line:
                continue
            normalized = command_line.lower()
            if "run_server.py" in normalized:
                web_processes.append(ManagedProcess(pid=pid, command_line=command_line))
            elif "manage.py qcluster" in normalized:
                qcluster_processes.append(ManagedProcess(pid=pid, command_line=command_line))
        return {
            "web": self._collapse_launcher_processes(web_processes, process_index),
            "qcluster": self._collapse_launcher_processes(qcluster_processes, process_index),
        }

    def _query_python_processes(self) -> list[dict]:
        command = (
            "Get-CimInstance Win32_Process | "
            "Where-Object { $_.Name -match 'python' -and $_.CommandLine } | "
            "Select-Object ProcessId, ParentProcessId, Name, CommandLine | ConvertTo-Json -Compress"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=str(self.project_root),
            capture_output=True,
            text=True,
            check=False,
            creationflags=creationflags,
        )
        if result.returncode != 0:
            return []
        payload = (result.stdout or "").strip()
        if not payload:
            return []
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _collapse_launcher_processes(
        self,
        processes: list[ManagedProcess],
        process_index: dict[int, dict],
    ) -> list[ManagedProcess]:
        if len(processes) < 2:
            return processes

        parent_pids = {
            int(process_index[item.pid].get("ParentProcessId") or 0)
            for item in processes
            if item.pid in process_index
        }
        collapsed = [item for item in processes if item.pid not in parent_pids]
        return collapsed or processes
