from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="NotificationTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("channel", models.CharField(choices=[("WHATSAPP", "WhatsApp")], default="WHATSAPP", max_length=30)),
                ("target_type", models.CharField(choices=[("PERSONAL", "Numero pessoal"), ("GROUP", "Grupo")], default="GROUP", max_length=20)),
                ("destination", models.CharField(help_text="Numero ou id do grupo. Ex: 120363020985287866@g.us", max_length=180)),
                ("enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Destino de notificacao",
                "verbose_name_plural": "Destinos de notificacao",
                "db_table": "notification_targets",
                "ordering": ["-enabled", "name"],
            },
        ),
        migrations.CreateModel(
            name="NotificationProviderConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="Evolution API", max_length=120)),
                ("provider_type", models.CharField(choices=[("EVOLUTION", "Evolution API (WhatsApp)")], default="EVOLUTION", max_length=30)),
                ("enabled", models.BooleanField(default=False)),
                ("endpoint_url", models.URLField(blank=True, help_text="URL completa do endpoint. Ex: http://host:8081/message/sendText/instancia")),
                ("api_key", models.CharField(blank=True, max_length=255)),
                ("timeout_seconds", models.PositiveIntegerField(default=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("default_target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="provider_defaults", to="notifications.notificationtarget")),
            ],
            options={
                "verbose_name": "Provider de notificacao",
                "verbose_name_plural": "Providers de notificacao",
                "db_table": "notification_provider_configs",
                "ordering": ["-enabled", "name"],
            },
        ),
        migrations.CreateModel(
            name="NotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_key", models.CharField(blank=True, max_length=120)),
                ("dedupe_key", models.CharField(blank=True, max_length=255)),
                ("destination_snapshot", models.CharField(blank=True, max_length=180)),
                ("message_preview", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("PENDING", "Pendente"), ("SENT", "Enviado"), ("FAILED", "Falhou"), ("SKIPPED_DUPLICATE", "Ignorado por duplicidade")], default="PENDING", max_length=30)),
                ("provider_response", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="notifications.notificationproviderconfig")),
                ("target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="notifications.notificationtarget")),
            ],
            options={
                "verbose_name": "Entrega de notificacao",
                "verbose_name_plural": "Entregas de notificacao",
                "db_table": "notification_deliveries",
                "ordering": ["-created_at"],
            },
        ),
    ]

