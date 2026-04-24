from django.db import models


class ScheduledJob(models.Model):
    JOB_TYPE_SYNC = "sync_spreadsheet"
    JOB_TYPE_BLOCK = "run_block"
    JOB_TYPE_CHOICES = (
        (JOB_TYPE_SYNC, "Sincronizar planilha"),
        (JOB_TYPE_BLOCK, "Executar block"),
    )

    SCHEDULE_INTERVAL = "interval"
    SCHEDULE_DAILY = "daily"
    SCHEDULE_MANUAL = "manual"
    SCHEDULE_TYPE_CHOICES = (
        (SCHEDULE_INTERVAL, "Intervalo"),
        (SCHEDULE_DAILY, "Horário diário"),
        (SCHEDULE_MANUAL, "Manual"),
    )

    STATUS_IDLE = "IDLE"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_ERROR = "ERROR"
    STATUS_RUNNING = "RUNNING"
    STATUS_SKIPPED = "SKIPPED"

    name = models.CharField(max_length=120, unique=True)
    job_type = models.CharField(max_length=40, choices=JOB_TYPE_CHOICES)
    enabled = models.BooleanField(default=True)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, default=SCHEDULE_INTERVAL)
    interval_minutes = models.PositiveIntegerField(blank=True, null=True)
    run_time = models.TimeField(blank=True, null=True)
    weekdays = models.CharField(max_length=32, blank=True, help_text="Opcional, formato 0,1,2 para seg-dom.")
    force_run = models.BooleanField(default=False)
    last_run_at = models.DateTimeField(blank=True, null=True)
    next_run_at = models.DateTimeField(blank=True, null=True)
    last_status = models.CharField(max_length=20, default=STATUS_IDLE)
    last_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scheduler_jobs"
        ordering = ["name"]
        verbose_name = "Job agendado"
        verbose_name_plural = "Jobs agendados"

    def __str__(self) -> str:
        return self.name


class JobExecution(models.Model):
    SOURCE_MANUAL = "MANUAL"
    SOURCE_SCHEDULER = "SCHEDULER"
    SOURCE_SERVICE_START = "SERVICE_START"
    SOURCE_CHOICES = (
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_SCHEDULER, "Scheduler"),
        (SOURCE_SERVICE_START, "Inicialização"),
    )

    STATUS_RUNNING = "RUNNING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_ERROR = "ERROR"
    STATUS_SKIPPED = "SKIPPED"

    job = models.ForeignKey(ScheduledJob, on_delete=models.CASCADE, related_name="executions")
    started_at = models.DateTimeField()
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default=STATUS_RUNNING)
    message = models.TextField(blank=True)
    result_payload = models.JSONField(blank=True, null=True)
    trigger_source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_SCHEDULER)

    class Meta:
        db_table = "scheduler_job_executions"
        ordering = ["-started_at"]
        verbose_name = "Execução do job"
        verbose_name_plural = "Execuções do job"

    def __str__(self) -> str:
        return f"{self.job.name} - {self.status} - {self.started_at:%d/%m/%Y %H:%M}"

