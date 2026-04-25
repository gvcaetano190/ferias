from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0005_seed_schedulersettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobexecution",
            name="cancel_requested",
            field=models.BooleanField(default=False),
        ),
    ]
