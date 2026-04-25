from django.db import migrations


def seed_scheduler_settings(apps, schema_editor):
    SchedulerSettings = apps.get_model("scheduler", "SchedulerSettings")
    if not SchedulerSettings.objects.exists():
        SchedulerSettings.objects.create(
            nome="Configuração principal",
            auto_start_with_server=False,
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0004_schedulersettings"),
    ]

    operations = [
        migrations.RunPython(seed_scheduler_settings, noop),
    ]
