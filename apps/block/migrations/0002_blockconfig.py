from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("block", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(default="Configuração principal", max_length=120)),
                ("usuario_teste_ad", models.CharField(blank=True, max_length=150)),
                ("ativo", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "block_configs",
                "ordering": ["-ativo", "nome"],
                "verbose_name": "Configuração Block",
                "verbose_name_plural": "Configurações Block",
            },
        ),
    ]
