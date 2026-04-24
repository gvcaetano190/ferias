from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0002_schedulerruntime"),
    ]

    operations = [
        migrations.AddField(
            model_name="schedulerruntime",
            name="process_id",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
