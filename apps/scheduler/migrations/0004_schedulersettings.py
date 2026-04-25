from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0003_schedulerruntime_process_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchedulerSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(default="Configuração principal", max_length=120)),
                ("auto_start_with_server", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "scheduler_settings",
                "ordering": ["id"],
                "verbose_name": "Configuração do scheduler",
                "verbose_name_plural": "Configurações do scheduler",
            },
        ),
    ]
