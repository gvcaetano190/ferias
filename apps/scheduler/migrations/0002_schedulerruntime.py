from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SchedulerRuntime",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.CharField(default="default", max_length=32, unique=True)),
                ("last_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("last_cycle_at", models.DateTimeField(blank=True, null=True)),
                ("last_status", models.CharField(default="STOPPED", max_length=20)),
                ("last_message", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "scheduler_runtime",
                "verbose_name": "Runtime do scheduler",
                "verbose_name_plural": "Runtime do scheduler",
            },
        ),
    ]
