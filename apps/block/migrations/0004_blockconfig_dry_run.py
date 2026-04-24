from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("block", "0003_blockprocessing_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="blockconfig",
            name="dry_run",
            field=models.BooleanField(default=False),
        ),
    ]
