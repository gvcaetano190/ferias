from django.contrib import admin

from apps.scheduler.models import JobExecution, ScheduledJob


@admin.register(ScheduledJob)
class ScheduledJobAdmin(admin.ModelAdmin):
    list_display = ("name", "job_type", "schedule_type", "enabled", "next_run_at", "last_status")
    list_filter = ("job_type", "schedule_type", "enabled", "last_status")
    search_fields = ("name", "last_message")
    readonly_fields = ("created_at", "updated_at", "last_run_at", "next_run_at", "last_status", "last_message")


@admin.register(JobExecution)
class JobExecutionAdmin(admin.ModelAdmin):
    list_display = ("job", "status", "trigger_source", "started_at", "finished_at")
    list_filter = ("status", "trigger_source", "job")
    search_fields = ("job__name", "message")
    readonly_fields = ("started_at", "finished_at", "result_payload")

