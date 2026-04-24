from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from apps.block.services import BlockService
from apps.shared.services.sync import SpreadsheetSyncService
from apps.scheduler.models import JobExecution, ScheduledJob
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
        while True:
            self.run_due_jobs()
            time.sleep(poll_seconds)

