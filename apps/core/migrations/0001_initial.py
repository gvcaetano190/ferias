from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="OperationalSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("company_name", models.CharField(default="Sistema de Controle de Férias", max_length=120)),
                ("google_sheets_url", models.URLField(blank=True)),
                ("sync_enabled", models.BooleanField(default=True)),
                ("cache_minutes", models.PositiveIntegerField(default=60)),
                ("onetimesecret_enabled", models.BooleanField(default=True)),
                ("onetimesecret_email", models.EmailField(blank=True, max_length=254)),
                ("onetimesecret_api_key", models.CharField(blank=True, max_length=255)),
                ("allowed_systems", models.JSONField(default=list, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuração operacional",
                "verbose_name_plural": "Configurações operacionais",
            },
        ),
    ]
