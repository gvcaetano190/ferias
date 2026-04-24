from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ScheduledJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("job_type", models.CharField(choices=[("sync_spreadsheet", "Sincronizar planilha"), ("run_block", "Executar block")], max_length=40)),
                ("enabled", models.BooleanField(default=True)),
                ("schedule_type", models.CharField(choices=[("interval", "Intervalo"), ("daily", "Horário diário"), ("manual", "Manual")], default="interval", max_length=20)),
                ("interval_minutes", models.PositiveIntegerField(blank=True, null=True)),
                ("run_time", models.TimeField(blank=True, null=True)),
                ("weekdays", models.CharField(blank=True, help_text="Opcional, formato 0,1,2 para seg-dom.", max_length=32)),
                ("force_run", models.BooleanField(default=False)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(default="IDLE", max_length=20)),
                ("last_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "scheduler_jobs",
                "ordering": ["name"],
                "verbose_name": "Job agendado",
                "verbose_name_plural": "Jobs agendados",
            },
        ),
        migrations.CreateModel(
            name="JobExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField()),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(default="RUNNING", max_length=20)),
                ("message", models.TextField(blank=True)),
                ("result_payload", models.JSONField(blank=True, null=True)),
                ("trigger_source", models.CharField(choices=[("MANUAL", "Manual"), ("SCHEDULER", "Scheduler"), ("SERVICE_START", "Inicialização")], default="SCHEDULER", max_length=20)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="scheduler.scheduledjob")),
            ],
            options={
                "db_table": "scheduler_job_executions",
                "ordering": ["-started_at"],
                "verbose_name": "Execução do job",
                "verbose_name_plural": "Execuções do job",
            },
        ),
    ]

