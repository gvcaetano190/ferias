from __future__ import annotations

import os
import platform
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from django.utils import timezone

from apps.block.services import BlockService
from apps.shared.services.sync import SpreadsheetSyncService
from apps.scheduler.models import JobExecution, ScheduledJob, SchedulerRuntime
from apps.scheduler.repositories import SchedulerRepository


@dataclass
class SchedulerRunResult:
    status: str
    message: str
    payload: dict


class SchedulerService:
    def __init__(self, repository: SchedulerRepository | None = None) -> None:
        self.repository = repository or SchedulerRepository()

    def ensure_default_jobs(self) -> None:
        defaults = [
            {
                "name": "Sincronização da planilha",
                "job_type": ScheduledJob.JOB_TYPE_SYNC,
                "schedule_type": ScheduledJob.SCHEDULE_INTERVAL,
                "interval_minutes": 60,
                "force_run": False,
            },
            {
                "name": "Verificação block",
                "job_type": ScheduledJob.JOB_TYPE_BLOCK,
                "schedule_type": ScheduledJob.SCHEDULE_INTERVAL,
                "interval_minutes": 30,
                "force_run": False,
            },
        ]
        now = timezone.now()
        for item in defaults:
            job, created = ScheduledJob.objects.get_or_create(
                name=item["name"],
                defaults={
                    **item,
                    "enabled": True,
                    "last_status": ScheduledJob.STATUS_IDLE,
                    "next_run_at": now,
                },
            )
            if created:
                job.next_run_at = self.calculate_next_run_at(job, now=now, just_ran=False)
                job.save(update_fields=["next_run_at"])

    def dashboard_data(self) -> dict:
        self.ensure_default_jobs()
        jobs = list(self.repository.list_jobs())
        executions = list(self.repository.recent_executions())
        runtime = self._runtime_status()
        summary = {
            "ativos": sum(1 for job in jobs if job.enabled),
            "com_erro": sum(1 for job in jobs if job.last_status == ScheduledJob.STATUS_ERROR),
            "rodando": sum(1 for job in jobs if job.last_status == ScheduledJob.STATUS_RUNNING),
            "proximos": sum(1 for job in jobs if job.next_run_at),
        }
        return {
            "summary": summary,
            "jobs": jobs,
            "executions": executions,
            "now": timezone.localtime(),
            "runtime": runtime,
        }

    def calculate_next_run_at(self, job: ScheduledJob, *, now=None, just_ran: bool = True):
        now = now or timezone.now()
        if job.schedule_type == ScheduledJob.SCHEDULE_MANUAL:
            return None

        if job.schedule_type == ScheduledJob.SCHEDULE_INTERVAL:
            minutes = max(1, job.interval_minutes or 1)
            base = now if just_ran or not job.next_run_at else job.next_run_at
            return base + timedelta(minutes=minutes)

        if job.schedule_type == ScheduledJob.SCHEDULE_DAILY and job.run_time:
            candidate = timezone.make_aware(
                datetime.combine(now.date(), job.run_time),
                timezone.get_current_timezone(),
            )
            if candidate <= now:
                candidate += timedelta(days=1)
            return candidate

        return now + timedelta(minutes=30)

    def run_job(self, job: ScheduledJob, *, trigger_source: str = JobExecution.SOURCE_MANUAL) -> SchedulerRunResult:
        running = self.repository.running_execution(job)
        if running:
            return SchedulerRunResult(
                status=JobExecution.STATUS_SKIPPED,
                message="Job já está em execução.",
                payload={"execution_id": running.pk},
            )

        started_at = timezone.now()
        execution = self.repository.create_execution(job=job, started_at=started_at, trigger_source=trigger_source)
        job.last_status = ScheduledJob.STATUS_RUNNING
        job.save(update_fields=["last_status", "updated_at"])

        try:
            result = self.execute_job(job)
            status = result.status
            message = result.message
            payload = result.payload
        except Exception as exc:
            status = JobExecution.STATUS_ERROR
            message = str(exc)
            payload = {"error": str(exc)}

        finished_at = timezone.now()
        self.repository.finish_execution(
            execution,
            status=status,
            finished_at=finished_at,
            message=message,
            result_payload=payload,
        )
        self.repository.update_job_after_run(
            job,
            now=finished_at,
            next_run_at=self.calculate_next_run_at(job, now=finished_at),
            status=status,
            message=message,
        )
        return SchedulerRunResult(status=status, message=message, payload=payload)

    def execute_job(self, job: ScheduledJob) -> SchedulerRunResult:
        if job.job_type == ScheduledJob.JOB_TYPE_SYNC:
            result = SpreadsheetSyncService().run(force=job.force_run)
            status = JobExecution.STATUS_SUCCESS if result.get("status") in {"success", "skipped"} else JobExecution.STATUS_ERROR
            return SchedulerRunResult(
                status=status,
                message=result.get("message", "Sincronização executada."),
                payload=result,
            )

        if job.job_type == ScheduledJob.JOB_TYPE_BLOCK:
            result = BlockService().processar_verificacao_block()
            return SchedulerRunResult(
                status=JobExecution.STATUS_SUCCESS,
                message=(
                    f"Block executado. "
                    f"Bloqueios={result['bloqueios_feitos']} "
                    f"Desbloqueios={result['desbloqueios_feitos']} "
                    f"Erros={result['erros']}"
                ),
                payload=result,
            )

        raise ValueError(f"Tipo de job não suportado: {job.job_type}")

    def run_due_jobs(self) -> list[SchedulerRunResult]:
        now = timezone.now()
        results = []
        for job in self.repository.due_jobs(now):
            results.append(self.run_job(job, trigger_source=JobExecution.SOURCE_SCHEDULER))
        return results

    def loop_forever(self, poll_seconds: int = 60) -> None:
        self.ensure_default_jobs()
        self._touch_runtime(status="RUNNING", message="Scheduler iniciado.", cycle=True)
        while True:
            self._touch_runtime(status="RUNNING", message="Aguardando próxima verificação.")
            self.run_due_jobs()
            self._touch_runtime(status="RUNNING", message="Ciclo concluído.", cycle=True)
            time.sleep(poll_seconds)

    def start_runtime(self) -> tuple[bool, str]:
        runtime = self._get_runtime()
        if self._is_process_alive(runtime.process_id):
            return False, "O scheduler já está rodando."

        if platform.system().lower() != "windows":
            return False, "O controle de iniciar/parar automático está preparado para Windows."

        project_root = Path(__file__).resolve().parents[2]
        python_exe = project_root / ".venv" / "Scripts" / "python.exe"
        runner = project_root / "run_scheduler.py"
        if not python_exe.exists():
            return False, "Python da .venv não encontrado. Rode o setup do Windows primeiro."
        if not runner.exists():
            return False, "run_scheduler.py não encontrado."

        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        process = subprocess.Popen(
            [str(python_exe), str(runner)],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        runtime.process_id = process.pid
        runtime.last_status = "STARTING"
        runtime.last_message = f"Scheduler iniciado pelo painel. PID {process.pid}."
        runtime.last_heartbeat_at = timezone.now()
        runtime.save(update_fields=["process_id", "last_status", "last_message", "last_heartbeat_at", "updated_at"])
        return True, f"Scheduler iniciado. PID {process.pid}."

    def stop_runtime(self) -> tuple[bool, str]:
        runtime = self._get_runtime()
        pid = runtime.process_id
        if not pid:
            runtime.last_status = "STOPPED"
            runtime.last_message = "Scheduler já estava parado."
            runtime.save(update_fields=["last_status", "last_message", "updated_at"])
            return False, "Scheduler já está parado."

        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 and self._is_process_alive(pid):
                message = (result.stderr or result.stdout or "Não foi possível parar o scheduler.").strip()
                return False, message
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as exc:
                return False, f"Não foi possível parar o scheduler: {exc}"

        runtime.process_id = None
        runtime.last_status = "STOPPED"
        runtime.last_message = "Scheduler parado pelo painel."
        runtime.save(update_fields=["process_id", "last_status", "last_message", "updated_at"])
        return True, "Scheduler parado com sucesso."

    def restart_runtime(self) -> tuple[bool, str]:
        stop_ok, stop_message = self.stop_runtime()
        if not stop_ok and "já está parado" not in stop_message.lower():
            return False, stop_message
        time.sleep(1)
        return self.start_runtime()

    def _runtime_status(self) -> dict:
        runtime = self._get_runtime()
        now = timezone.now()
        threshold_seconds = int(timezone.timedelta(minutes=3).total_seconds())
        is_alive = False
        if runtime.last_heartbeat_at:
            is_alive = (now - runtime.last_heartbeat_at).total_seconds() <= threshold_seconds
        if runtime.process_id and not self._is_process_alive(runtime.process_id):
            runtime.process_id = None
            runtime.last_status = "STOPPED"
            runtime.last_message = "Processo do scheduler não está mais em execução."
            runtime.save(update_fields=["process_id", "last_status", "last_message", "updated_at"])
            is_alive = False
        return {
            "is_running": is_alive,
            "label": "Rodando" if is_alive else "Parado",
            "can_start": not is_alive,
            "can_stop": bool(runtime.process_id) or is_alive,
            "process_id": runtime.process_id,
            "last_heartbeat_at": runtime.last_heartbeat_at,
            "last_cycle_at": runtime.last_cycle_at,
            "last_message": runtime.last_message,
        }

    def _touch_runtime(self, *, status: str, message: str, cycle: bool = False) -> None:
        runtime = self._get_runtime()
        runtime.last_status = status
        runtime.last_message = message
        runtime.last_heartbeat_at = timezone.now()
        runtime.process_id = os.getpid()
        if cycle:
            runtime.last_cycle_at = runtime.last_heartbeat_at
        runtime.save(update_fields=["process_id", "last_status", "last_message", "last_heartbeat_at", "last_cycle_at", "updated_at"])

    def _get_runtime(self) -> SchedulerRuntime:
        runtime, _ = SchedulerRuntime.objects.get_or_create(singleton_key="default")
        return runtime

    def _is_process_alive(self, pid: int | None) -> bool:
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
