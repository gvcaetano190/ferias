from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from apps.core.models import OperationalSettings

class ApplicationControlService:
    def restart_web_application(self) -> tuple[bool, str]:
        if platform.system().lower() != "windows":
            return False, "O reinício automático da aplicação foi preparado apenas para Windows."

        project_root = Path(__file__).resolve().parents[2]
        helper_script = project_root / "restart_application_helper.py"
        if not helper_script.exists():
            return False, "Helper de reinício não encontrado."

        current_pid = os.getpid()
        scheduler_pid = 0
        restart_scheduler = False

        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        creationflags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

        subprocess.Popen(
            [
                str(project_root / ".venv" / "Scripts" / "python.exe"),
                str(helper_script),
                "--server-pid",
                str(current_pid),
                "--scheduler-pid",
                str(scheduler_pid),
                "--restart-scheduler",
                "1" if restart_scheduler else "0",
            ],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        return True, "Reinício da aplicação solicitado. A conexão pode cair por alguns segundos."
