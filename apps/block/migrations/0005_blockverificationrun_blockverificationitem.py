from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("block", "0004_blockconfig_dry_run"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockVerificationRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(default="SUCCESS", max_length=20)),
                ("total_inicial_bloqueio", models.PositiveIntegerField(default=0)),
                ("total_inicial_desbloqueio", models.PositiveIntegerField(default=0)),
                ("total_final_bloqueio", models.PositiveIntegerField(default=0)),
                ("total_final_desbloqueio", models.PositiveIntegerField(default=0)),
                ("total_sincronizados", models.PositiveIntegerField(default=0)),
                ("total_ignorados", models.PositiveIntegerField(default=0)),
                ("total_erros", models.PositiveIntegerField(default=0)),
                ("summary_message", models.TextField(blank=True)),
            ],
            options={
                "verbose_name": "Verificação operacional do block",
                "verbose_name_plural": "Verificações operacionais do block",
                "db_table": "block_verification_runs",
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="BlockVerificationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("colaborador_id", models.IntegerField(db_index=True)),
                ("colaborador_nome", models.CharField(max_length=255)),
                ("usuario_ad", models.CharField(blank=True, max_length=150)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("data_saida", models.DateField(blank=True, null=True)),
                ("data_retorno", models.DateField(blank=True, null=True)),
                ("acao_inicial", models.CharField(choices=[("BLOQUEAR", "Bloquear"), ("DESBLOQUEAR", "Desbloquear"), ("IGNORAR", "Ignorar")], max_length=20)),
                ("acao_final", models.CharField(choices=[("BLOQUEAR", "Bloquear"), ("DESBLOQUEAR", "Desbloquear"), ("IGNORAR", "Ignorar")], max_length=20)),
                ("resultado_verificacao", models.CharField(choices=[("MANTIDO", "Mantido"), ("REMOVIDO_DA_FILA", "Removido da fila"), ("SINCRONIZADO", "Sincronizado"), ("ERRO_VERIFICACAO", "Erro de verificacao")], max_length=30)),
                ("ad_status_banco_antes", models.CharField(blank=True, max_length=50)),
                ("vpn_status_banco_antes", models.CharField(blank=True, max_length=50)),
                ("ad_status_real", models.CharField(blank=True, max_length=50)),
                ("vpn_status_real", models.CharField(blank=True, max_length=50)),
                ("ad_status_banco_depois", models.CharField(blank=True, max_length=50)),
                ("vpn_status_banco_depois", models.CharField(blank=True, max_length=50)),
                ("motivo", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="items", to="block.blockverificationrun")),
            ],
            options={
                "verbose_name": "Item da verificação block",
                "verbose_name_plural": "Itens da verificação block",
                "db_table": "block_verification_items",
                "ordering": ["run_id", "colaborador_nome", "usuario_ad"],
            },
        ),
    ]
