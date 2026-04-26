from __future__ import annotations

import argparse
import os
import platform
import signal
import subprocess
import time
from pathlib import Path


def is_process_alive(pid: int) -> bool:
    if not pid:
        return False
    if platform.system().lower() == "windows":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_process(pid: int) -> None:
    if not pid or not is_process_alive(pid):
        return
    if platform.system().lower() == "windows":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return


def start_hidden_batch(batch_path: Path, project_root: Path) -> None:
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-Command",
            (
                f"Start-Process -FilePath '{batch_path}' "
                f"-WorkingDirectory '{project_root}' -WindowStyle Hidden"
            ),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-pid", type=int, default=0)
    parser.add_argument("--scheduler-pid", type=int, default=0)
    parser.add_argument("--restart-scheduler", default="0")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    time.sleep(2)

    stop_process(args.server_pid)
    if args.scheduler_pid:
        stop_process(args.scheduler_pid)
    time.sleep(2)

    start_hidden_batch(project_root / "start_server.bat", project_root)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
