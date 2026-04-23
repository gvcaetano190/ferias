from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BlockProcessing",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("colaborador_id", models.IntegerField(db_index=True)),
                ("usuario_ad", models.CharField(blank=True, max_length=150)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("acao", models.CharField(max_length=20)),
                ("ad_status", models.CharField(blank=True, max_length=50)),
                ("vpn_status", models.CharField(blank=True, max_length=50)),
                ("resultado", models.CharField(max_length=20)),
                ("mensagem", models.TextField(blank=True)),
                ("executado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "db_table": "block_processings",
                "ordering": ["-executado_em"],
                "verbose_name": "Processamento Block",
                "verbose_name_plural": "Processamentos Block",
            },
        ),
    ]
