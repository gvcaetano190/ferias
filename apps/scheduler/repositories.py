from __future__ import annotations

from django.db.models import QuerySet

from apps.scheduler.models import JobExecution, ScheduledJob


class SchedulerRepository:
    def list_jobs(self) -> QuerySet[ScheduledJob]:
        return ScheduledJob.objects.order_by("name")

    def active_jobs(self) -> QuerySet[ScheduledJob]:
        return ScheduledJob.objects.filter(enabled=True).order_by("name")

    def due_jobs(self, now) -> QuerySet[ScheduledJob]:
        return (
            ScheduledJob.objects.filter(enabled=True)
            .filter(next_run_at__isnull=False, next_run_at__lte=now)
            .order_by("next_run_at", "name")
        )

    def get_job(self, pk: int) -> ScheduledJob | None:
        try:
            return ScheduledJob.objects.get(pk=pk)
        except ScheduledJob.DoesNotExist:
            return None

    def recent_executions(self, limit: int = 20) -> QuerySet[JobExecution]:
        return JobExecution.objects.select_related("job").order_by("-started_at")[:limit]

    def running_execution(self, job: ScheduledJob) -> JobExecution | None:
        return (
            JobExecution.objects.filter(job=job, status=JobExecution.STATUS_RUNNING, finished_at__isnull=True)
            .order_by("-started_at")
            .first()
        )

    def create_execution(self, *, job: ScheduledJob, started_at, trigger_source: str) -> JobExecution:
        return JobExecution.objects.create(
            job=job,
            started_at=started_at,
            trigger_source=trigger_source,
            status=JobExecution.STATUS_RUNNING,
        )

    def finish_execution(self, execution: JobExecution, *, status: str, finished_at, message: str, result_payload) -> None:
        execution.status = status
        execution.finished_at = finished_at
        execution.message = message
        execution.result_payload = result_payload
        execution.save(update_fields=["status", "finished_at", "message", "result_payload"])

    def update_job_after_run(self, job: ScheduledJob, *, now, next_run_at, status: str, message: str) -> None:
        job.last_run_at = now
        job.next_run_at = next_run_at
        job.last_status = status
        job.last_message = message
        job.save(update_fields=["last_run_at", "next_run_at", "last_status", "last_message", "updated_at"])

