from django import forms
from django.contrib import admin

from apps.scheduler.models import JobExecution, ScheduledJob


class ScheduledJobAdminForm(forms.ModelForm):
    WEEKDAY_CHOICES = (
        ("0", "Seg"),
        ("1", "Ter"),
        ("2", "Qua"),
        ("3", "Qui"),
        ("4", "Sex"),
        ("5", "Sáb"),
        ("6", "Dom"),
    )

    weekdays_selection = forms.MultipleChoiceField(
        label="Dias da semana",
        choices=WEEKDAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Marque os dias em que o job pode rodar. Para segunda a segunda, marque todos.",
    )

    class Meta:
        model = ScheduledJob
        fields = "__all__"
        widgets = {
            "run_time": forms.TimeInput(
                format="%H:%M",
                attrs={
                    "type": "time",
                    "step": 60,
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["schedule_type"].choices = [
            choice for choice in self.fields["schedule_type"].choices
            if choice[0] != ScheduledJob.SCHEDULE_INTERVAL
        ]
        self.fields["run_time"].input_formats = ["%H:%M"]
        self.fields["run_time"].help_text = (
            "Use HH:MM. Para rodar em dois horários no dia, crie dois jobs diários separados."
        )
        self.fields.pop("interval_minutes", None)
        self.fields["weekdays_selection"].initial = [
            item.strip()
            for item in (self.instance.weekdays or "").split(",")
            if item.strip()
        ]

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["weekdays"] = ",".join(cleaned_data.get("weekdays_selection") or [])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.weekdays = self.cleaned_data.get("weekdays", "")
        if commit:
            instance.save()
        return instance


@admin.register(ScheduledJob)
class ScheduledJobAdmin(admin.ModelAdmin):
    form = ScheduledJobAdminForm
    list_display = ("name", "job_type", "schedule_type", "enabled", "next_run_at", "last_status")
    list_filter = ("job_type", "schedule_type", "enabled", "last_status")
    search_fields = ("name", "last_message")
    readonly_fields = ("created_at", "updated_at", "last_run_at", "next_run_at", "last_status", "last_message")
    fieldsets = (
        (
            "Configuração",
            {
                "fields": (
                    "name",
                    "job_type",
                    "enabled",
                    "schedule_type",
                    "run_time",
                    "weekdays_selection",
                    "force_run",
                )
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "last_run_at",
                    "next_run_at",
                    "last_status",
                    "last_message",
                )
            },
        ),
    )


@admin.register(JobExecution)
class JobExecutionAdmin(admin.ModelAdmin):
    list_display = ("job", "status", "trigger_source", "started_at", "finished_at")
    list_filter = ("status", "trigger_source", "job")
    search_fields = ("job__name", "message")
    readonly_fields = ("started_at", "finished_at", "result_payload")
