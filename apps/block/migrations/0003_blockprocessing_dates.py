from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("block", "0002_blockconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="blockprocessing",
            name="data_retorno",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="blockprocessing",
            name="data_saida",
            field=models.DateField(blank=True, null=True),
        ),
    ]
