from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0007_jobexecution_cancel_requested_db_default"),
    ]

    operations = [
        migrations.AlterField(
            model_name="jobexecution",
            name="cancel_requested",
            field=models.BooleanField(blank=True, db_default=False, default=False, null=True),
        ),
    ]
