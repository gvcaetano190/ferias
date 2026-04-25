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
    RUNTIME_HEARTBEAT_TIMEOUT_SECONDS = 180
    EXECUTION_STALE_TIMEOUT_MINUTES = 15
    STARTUP_GRACE_SECONDS = 300
    JOB_PRIORITIES = {
        ScheduledJob.JOB_TYPE_SYNC: 0,
        ScheduledJob.JOB_TYPE_VERIFY_BLOCK: 1,
        ScheduledJob.JOB_TYPE_BLOCK: 2,
    }
    DEFAULT_JOBS = (
        {
            "name": "Sincronização da planilha",
            "job_type": ScheduledJob.JOB_TYPE_SYNC,
            "schedule_type": ScheduledJob.SCHEDULE_INTERVAL,
            "interval_minutes": 60,
            "force_run": False,
        },
        {
            "name": "Verificação operacional block",
            "job_type": ScheduledJob.JOB_TYPE_VERIFY_BLOCK,
            "schedule_type": ScheduledJob.SCHEDULE_INTERVAL,
            "interval_minutes": 20,
            "force_run": False,
        },
        {
            "name": "Verificação block",
            "job_type": ScheduledJob.JOB_TYPE_BLOCK,
            "schedule_type": ScheduledJob.SCHEDULE_INTERVAL,
            "interval_minutes": 30,
            "force_run": False,
        },
    )

    def __init__(self, repository: SchedulerRepository | None = None) -> None:
        self.repository = repository or SchedulerRepository()

    def ensure_default_jobs(self) -> None:
        now = timezone.now()
        for item in self.DEFAULT_JOBS:
            job = self._get_or_create_default_job(item, now=now)
            if job.next_run_at is None:
                job.next_run_at = self.calculate_next_run_at(job, now=now, just_ran=False)
                job.save(update_fields=["next_run_at"])

    def dashboard_data(self) -> dict:
        self.ensure_default_jobs()
        runtime = self._runtime_status()
        self._reconcile_stale_executions(now=timezone.now(), scheduler_running=runtime["is_running"])
        jobs = list(self.repository.list_jobs())
        executions = list(self.repository.recent_executions())
        runtime = self._runtime_status()
        running_jobs = list(self.repository.running_executions())
        summary = {
            "ativos": sum(1 for job in jobs if job.enabled),
            "com_erro": sum(1 for job in jobs if job.last_status == ScheduledJob.STATUS_ERROR),
            "rodando": len(running_jobs),
            "proximos": sum(1 for job in jobs if job.next_run_at),
        }
        return {
            "summary": summary,
            "jobs": jobs,
            "executions": executions,
            "running_executions": running_jobs,
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
                message="Job ja esta em execucao.",
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
        execution.refresh_from_db()
        if execution.finished_at is not None:
            return SchedulerRunResult(
                status=execution.status,
                message=execution.message,
                payload=execution.result_payload or {},
            )
        if execution.cancel_requested:
            status = JobExecution.STATUS_ERROR
            message = "Parada solicitada pelo painel. A task foi finalizada sem interromper o servico do scheduler."
            payload = {
                **payload,
                "cancel_requested": True,
            }
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
        job_type = (job.job_type or "").strip().lower()

        if job_type == ScheduledJob.JOB_TYPE_SYNC:
            result = SpreadsheetSyncService().run(force=job.force_run)
            status = (
                JobExecution.STATUS_SUCCESS
                if result.get("status") in {"success", "skipped"}
                else JobExecution.STATUS_ERROR
            )
            return SchedulerRunResult(
                status=status,
                message=result.get("message", "Sincronizacao executada."),
                payload=result,
            )

        if job_type in {ScheduledJob.JOB_TYPE_VERIFY_BLOCK, "verify_block_candidates"}:
            result = BlockService().processar_verificacao_operacional_block()
            return SchedulerRunResult(
                status=JobExecution.STATUS_SUCCESS,
                message=result.get("summary_message", "Verificacao operacional do block concluida."),
                payload=result,
            )

        if job_type == ScheduledJob.JOB_TYPE_BLOCK:
            result = BlockService().processar_verificacao_block(require_operational_queue=True)
            if result.get("skipped"):
                return SchedulerRunResult(
                    status=JobExecution.STATUS_SKIPPED,
                    message=result.get("message", "Block aguardando fila operacional valida."),
                    payload=result,
                )
            return SchedulerRunResult(
                status=JobExecution.STATUS_SUCCESS,
                message=(
                    f"{'Block simulado' if result.get('dry_run') else 'Block executado'}. "
                    f"Bloqueios={result['bloqueios_feitos']} "
                    f"Desbloqueios={result['desbloqueios_feitos']} "
                    f"Erros={result['erros']}"
                ),
                payload=result,
            )

        raise ValueError(f"Tipo de job nao suportado: {job.job_type}")

    def run_due_jobs(self) -> list[SchedulerRunResult]:
        now = timezone.now()
        results = []
        due_jobs = list(self.repository.due_jobs(now))
        due_jobs.sort(
            key=lambda job: (
                self.JOB_PRIORITIES.get(job.job_type, 99),
                job.next_run_at or now,
                job.name,
            )
        )
        if due_jobs:
            results.append(self.run_job(due_jobs[0], trigger_source=JobExecution.SOURCE_SCHEDULER))
        return results

    def loop_forever(self, poll_seconds: int = 60) -> None:
        self.ensure_default_jobs()
        self._touch_runtime(status="RUNNING", message="Scheduler iniciado.", cycle=True)
        self._aguardar_janela_inicial(poll_seconds=poll_seconds)
        while True:
            self._touch_runtime(status="RUNNING", message="Aguardando proxima verificacao.")
            self.run_due_jobs()
            self._touch_runtime(status="RUNNING", message="Ciclo concluido.", cycle=True)
            time.sleep(poll_seconds)

    def start_runtime(self) -> tuple[bool, str]:
        runtime = self._get_runtime()
        if self._is_process_alive(runtime.process_id):
            return False, "O scheduler ja esta rodando."

        if platform.system().lower() != "windows":
            return False, "O controle automatico foi preparado para Windows."

        project_root = Path(__file__).resolve().parents[2]
        python_exe = project_root / ".venv" / "Scripts" / "python.exe"
        runner = project_root / "run_scheduler.py"
        if not python_exe.exists():
            return False, "Python da .venv nao encontrado. Rode o setup do Windows primeiro."
        if not runner.exists():
            return False, "run_scheduler.py nao encontrado."

        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
        python_launcher = python_exe
        pythonw_exe = project_root / ".venv" / "Scripts" / "pythonw.exe"
        if pythonw_exe.exists():
            python_launcher = pythonw_exe

        process = subprocess.Popen(
            [str(python_launcher), str(runner)],
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
        runtime.last_heartbeat_at = None
        runtime.last_cycle_at = None
        runtime.save(
            update_fields=["process_id", "last_status", "last_message", "last_heartbeat_at", "last_cycle_at", "updated_at"]
        )

        time.sleep(2)
        runtime_status = self._runtime_status()
        if runtime_status["is_running"]:
            return True, (
                f"Scheduler iniciado em background. PID {process.pid}. "
                f"Os jobs aguardarao {self.STARTUP_GRACE_SECONDS // 60} minutos antes do primeiro ciclo."
            )
        if self._is_process_alive(process.pid):
            return True, (
                f"Scheduler em inicializacao. PID {process.pid}. "
                f"Os jobs aguardarao {self.STARTUP_GRACE_SECONDS // 60} minutos antes do primeiro ciclo."
            )

        runtime.refresh_from_db()
        runtime.process_id = None
        runtime.last_status = "STOPPED"
        runtime.last_message = "Falha ao iniciar o scheduler em background."
        runtime.save(update_fields=["process_id", "last_status", "last_message", "updated_at"])
        return False, "Falha ao iniciar o scheduler. Verifique a configuracao do ambiente."

    def stop_runtime(self) -> tuple[bool, str]:
        runtime = self._get_runtime()
        pid = runtime.process_id
        if not pid:
            runtime.last_status = "STOPPED"
            runtime.last_message = "Scheduler ja estava parado."
            runtime.save(update_fields=["last_status", "last_message", "updated_at"])
            self._clear_running_executions(reason="Servico parado pelo painel com runtime ja sem PID.")
            return False, "Scheduler ja esta parado."

        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0 and self._is_process_alive(pid):
                message = (result.stderr or result.stdout or "Nao foi possivel parar o scheduler.").strip()
                return False, message
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as exc:
                return False, f"Nao foi possivel parar o scheduler: {exc}"

        runtime.process_id = None
        runtime.last_status = "STOPPED"
        runtime.last_message = "Scheduler parado pelo painel."
        runtime.save(update_fields=["process_id", "last_status", "last_message", "updated_at"])
        self._clear_running_executions(reason="Servico parado pelo painel.")
        return True, "Scheduler parado com sucesso."

    def restart_runtime(self) -> tuple[bool, str]:
        stop_ok, stop_message = self.stop_runtime()
        if not stop_ok and "ja esta parado" not in stop_message.lower():
            return False, stop_message
        time.sleep(1)
        return self.start_runtime()

    def force_stop_targets(self) -> dict:
        running_executions = list(self.repository.running_executions())
        return {
            "targets": [
                {
                    "execution_id": execution.id,
                    "job_name": execution.job.name,
                    "trigger_source": execution.trigger_source,
                    "started_at": execution.started_at,
                    "status": execution.status,
                    "mode": "request_cancel" if self._execution_has_live_runtime(execution) else "clear_record",
                }
                for execution in running_executions
            ],
        }

    def force_stop_execution(self, execution_id: int) -> tuple[bool, str]:
        execution = self.repository.get_execution(execution_id)
        if not execution:
            return False, "Execucao nao encontrada."
        if execution.status != JobExecution.STATUS_RUNNING or execution.finished_at is not None:
            return False, "Essa task nao esta mais rodando."

        if self._execution_has_live_runtime(execution):
            execution.cancel_requested = True
            execution.message = "Parada solicitada pelo painel; aguardando conclusao segura da task."
            execution.save(update_fields=["cancel_requested", "message"])
            execution.job.last_message = "Parada solicitada pelo painel para esta task. O servico do scheduler continua rodando."
            execution.job.save(update_fields=["last_message", "updated_at"])
            return True, f"Solicitacao registrada para a task {execution.job.name}. O servico do scheduler permanece ativo."

        now = timezone.now()
        self.repository.finish_execution(
            execution,
            status=JobExecution.STATUS_ERROR,
            finished_at=now,
            message="Task encerrada manualmente pelo painel.",
            result_payload={"error": "force_stopped_by_user"},
        )
        execution.job.last_status = ScheduledJob.STATUS_ERROR
        execution.job.last_message = "Task encerrada manualmente pelo painel."
        execution.job.save(update_fields=["last_status", "last_message", "updated_at"])
        return True, f"Task {execution.job.name} encerrada no painel."

    def _runtime_status(self) -> dict:
        runtime = self._get_runtime()
        now = timezone.now()
        heartbeat_is_recent = False
        if runtime.last_heartbeat_at:
            heartbeat_is_recent = (
                now - runtime.last_heartbeat_at
            ).total_seconds() <= self.RUNTIME_HEARTBEAT_TIMEOUT_SECONDS

        process_is_alive = self._is_process_alive(runtime.process_id)
        if runtime.process_id and not process_is_alive:
            runtime.process_id = None
            runtime.last_status = "STOPPED"
            runtime.last_message = "Processo do scheduler nao esta mais em execucao."
            runtime.save(update_fields=["process_id", "last_status", "last_message", "updated_at"])
            process_is_alive = False

        if runtime.process_id is None and runtime.last_status == "RUNNING":
            runtime.last_status = "STOPPED"
            runtime.last_message = "Scheduler sem PID ativo; status reajustado automaticamente."
            runtime.save(update_fields=["last_status", "last_message", "updated_at"])

        is_starting = bool(runtime.process_id and process_is_alive and not heartbeat_is_recent)
        is_running = bool(runtime.process_id and process_is_alive and heartbeat_is_recent)
        return {
            "is_running": is_running,
            "is_starting": is_starting,
            "label": "Rodando" if is_running else "Iniciando" if is_starting else "Parado",
            "can_start": not (is_running or is_starting),
            "can_stop": bool(runtime.process_id and process_is_alive),
            "process_id": runtime.process_id,
            "last_heartbeat_at": runtime.last_heartbeat_at,
            "last_cycle_at": runtime.last_cycle_at,
            "last_message": runtime.last_message,
        }

    def _reconcile_stale_executions(self, *, now, scheduler_running: bool) -> None:
        if scheduler_running:
            return

        stale_before = now - timedelta(minutes=self.EXECUTION_STALE_TIMEOUT_MINUTES)
        running_executions = self.repository.running_executions()
        stale_executions = list(running_executions.filter(trigger_source=JobExecution.SOURCE_SCHEDULER))
        stale_executions.extend(
            list(
                running_executions.exclude(trigger_source=JobExecution.SOURCE_SCHEDULER).filter(started_at__lt=stale_before)
            )
        )
        for execution in stale_executions:
            self.repository.finish_execution(
                execution,
                status=JobExecution.STATUS_ERROR,
                finished_at=now,
                message=execution.message or "Execucao encerrada porque o runtime do scheduler nao estava ativo.",
                result_payload={"error": "scheduler_runtime_lost"},
            )
            job = execution.job
            if job.last_status == ScheduledJob.STATUS_RUNNING:
                job.last_status = ScheduledJob.STATUS_ERROR
                job.last_message = "Job estava RUNNING, mas o scheduler nao estava ativo; status ajustado."
                job.save(update_fields=["last_status", "last_message", "updated_at"])

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

    def _execution_has_live_runtime(self, execution: JobExecution) -> bool:
        runtime = self._get_runtime()
        return execution.trigger_source == JobExecution.SOURCE_SCHEDULER and self._is_process_alive(runtime.process_id)

    def _aguardar_janela_inicial(self, *, poll_seconds: int) -> None:
        grace_until = timezone.now() + timedelta(seconds=self.STARTUP_GRACE_SECONDS)
        while True:
            now = timezone.now()
            if now >= grace_until:
                self._touch_runtime(status="RUNNING", message="Janela inicial concluida; scheduler liberado para executar jobs.")
                return
            remaining_seconds = max(1, int((grace_until - now).total_seconds()))
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            self._touch_runtime(
                status="RUNNING",
                message=(
                    "Scheduler em espera apos iniciar. "
                    f"Primeiro ciclo automatico liberado em aproximadamente {remaining_minutes} minuto(s)."
                ),
            )
            time.sleep(min(poll_seconds, remaining_seconds))

    def _clear_running_executions(self, *, reason: str) -> None:
        now = timezone.now()
        for execution in self.repository.running_executions():
            self.repository.finish_execution(
                execution,
                status=JobExecution.STATUS_ERROR,
                finished_at=now,
                message=reason,
                result_payload={"error": "scheduler_stopped_by_user"},
            )
            job = execution.job
            job.last_status = ScheduledJob.STATUS_ERROR
            job.last_message = reason
            job.save(update_fields=["last_status", "last_message", "updated_at"])

    def _get_or_create_default_job(self, item: dict, *, now):
        jobs = list(
            ScheduledJob.objects.filter(job_type=item["job_type"]).order_by("id")
        )
        if not jobs:
            job = ScheduledJob.objects.create(
                **item,
                enabled=True,
                last_status=ScheduledJob.STATUS_IDLE,
                next_run_at=now,
            )
            return job

        primary = jobs[0]
        duplicates = jobs[1:]
        if duplicates:
            JobExecution.objects.filter(job__in=duplicates).update(job=primary)
            ScheduledJob.objects.filter(pk__in=[job.pk for job in duplicates]).delete()

        fields_to_update = []
        for field, value in item.items():
            if getattr(primary, field) != value:
                setattr(primary, field, value)
                fields_to_update.append(field)

        if not primary.enabled:
            primary.enabled = True
            fields_to_update.append("enabled")

        if primary.next_run_at is None:
            primary.next_run_at = now
            fields_to_update.append("next_run_at")

        if fields_to_update:
            primary.save(update_fields=fields_to_update + ["updated_at"])

        return primary

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
