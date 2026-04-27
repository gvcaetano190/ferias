from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationDivergenceAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_module", models.CharField(choices=[("BLOCK_OPERATIONAL", "Check operacional do block")], default="BLOCK_OPERATIONAL", max_length=40)),
                ("divergence_type", models.CharField(choices=[("BLOCK_ALREADY_BLOCKED", "Planilha pedia bloqueio, mas o AD ja estava bloqueado"), ("UNBLOCK_ALREADY_RELEASED", "Planilha pedia desbloqueio, mas o AD ja estava liberado")], max_length=60)),
                ("dedupe_key", models.CharField(max_length=255, unique=True)),
                ("collaborator_id", models.PositiveIntegerField(db_index=True)),
                ("collaborator_name", models.CharField(max_length=255)),
                ("usuario_ad", models.CharField(blank=True, max_length=150)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("system_name", models.CharField(default="AD PRIN", max_length=150)),
                ("initial_action", models.CharField(blank=True, max_length=20)),
                ("sheet_status", models.CharField(blank=True, max_length=50)),
                ("real_status", models.CharField(blank=True, max_length=50)),
                ("internal_status_after_sync", models.CharField(blank=True, max_length=50)),
                ("data_saida", models.DateField(blank=True, null=True)),
                ("data_retorno", models.DateField(blank=True, null=True)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Auditoria de divergencia",
                "verbose_name_plural": "Auditorias de divergencia",
                "db_table": "notification_divergence_audits",
                "ordering": ["-created_at"],
            },
        ),
    ]
