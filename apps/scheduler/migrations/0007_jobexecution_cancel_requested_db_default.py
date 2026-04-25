from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0006_jobexecution_cancel_requested"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobexecution",
            name="cancel_requested",
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
