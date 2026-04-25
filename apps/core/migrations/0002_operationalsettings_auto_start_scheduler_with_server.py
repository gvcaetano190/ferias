from django.db import migrations, models


def copy_scheduler_auto_start(apps, schema_editor):
    OperationalSettings = apps.get_model("core", "OperationalSettings")
    SchedulerSettings = apps.get_model("scheduler", "SchedulerSettings")

    operational, _ = OperationalSettings.objects.get_or_create(pk=1)
    scheduler_settings = SchedulerSettings.objects.order_by("id").first()
    if scheduler_settings is not None:
        operational.auto_start_scheduler_with_server = scheduler_settings.auto_start_with_server
        operational.save(update_fields=["auto_start_scheduler_with_server"])


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0008_jobexecution_cancel_requested_nullable"),
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="operationalsettings",
            name="auto_start_scheduler_with_server",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(copy_scheduler_auto_start, noop),
    ]
