from __future__ import annotations

from django.db import models


class NotificationTarget(models.Model):
    CHANNEL_WHATSAPP = "WHATSAPP"
    CHANNEL_CHOICES = (
        (CHANNEL_WHATSAPP, "WhatsApp"),
    )

    TYPE_PERSONAL = "PERSONAL"
    TYPE_GROUP = "GROUP"
    TARGET_TYPE_CHOICES = (
        (TYPE_PERSONAL, "Numero pessoal"),
        (TYPE_GROUP, "Grupo"),
    )

    name = models.CharField(max_length=120)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES, default=CHANNEL_WHATSAPP)
    target_type = models.CharField(max_length=20, choices=TARGET_TYPE_CHOICES, default=TYPE_GROUP)
    destination = models.CharField(max_length=180, help_text="Numero ou id do grupo. Ex: 120363020985287866@g.us")
    enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_targets"
        ordering = ["-enabled", "name"]
        verbose_name = "Destino de notificacao"
        verbose_name_plural = "Destinos de notificacao"

    def __str__(self) -> str:
        return self.name


class NotificationProviderConfig(models.Model):
    TYPE_EVOLUTION = "EVOLUTION"
    PROVIDER_TYPE_CHOICES = (
        (TYPE_EVOLUTION, "Evolution API (WhatsApp)"),
    )

    name = models.CharField(max_length=120, default="Evolution API")
    provider_type = models.CharField(max_length=30, choices=PROVIDER_TYPE_CHOICES, default=TYPE_EVOLUTION)
    enabled = models.BooleanField(default=False)
    endpoint_url = models.URLField(blank=True, help_text="URL completa do endpoint. Ex: http://host:8081/message/sendText/instancia")
    api_key = models.CharField(max_length=255, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=30)
    default_target = models.ForeignKey(
        NotificationTarget,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="provider_defaults",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_provider_configs"
        ordering = ["-enabled", "name"]
        verbose_name = "Provider de notificacao"
        verbose_name_plural = "Providers de notificacao"

    def __str__(self) -> str:
        return self.name


class NotificationDelivery(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_SENT = "SENT"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED_DUPLICATE"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pendente"),
        (STATUS_SENT, "Enviado"),
        (STATUS_FAILED, "Falhou"),
        (STATUS_SKIPPED, "Ignorado por duplicidade"),
    )

    event_key = models.CharField(max_length=120, blank=True)
    dedupe_key = models.CharField(max_length=255, blank=True)
    provider = models.ForeignKey(NotificationProviderConfig, on_delete=models.SET_NULL, null=True, blank=True)
    target = models.ForeignKey(NotificationTarget, on_delete=models.SET_NULL, null=True, blank=True)
    destination_snapshot = models.CharField(max_length=180, blank=True)
    message_preview = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notification_deliveries"
        ordering = ["-created_at"]
        verbose_name = "Entrega de notificacao"
        verbose_name_plural = "Entregas de notificacao"

    def __str__(self) -> str:
        return f"{self.event_key or 'teste'} - {self.status}"


class NotificationDivergenceAudit(models.Model):
    SOURCE_BLOCK_OPERATIONAL = "BLOCK_OPERATIONAL"
    SOURCE_CHOICES = (
        (SOURCE_BLOCK_OPERATIONAL, "Check operacional do block"),
    )

    TYPE_BLOCK_ALREADY_BLOCKED = "BLOCK_ALREADY_BLOCKED"
    TYPE_UNBLOCK_ALREADY_RELEASED = "UNBLOCK_ALREADY_RELEASED"
    DIVERGENCE_TYPE_CHOICES = (
        (TYPE_BLOCK_ALREADY_BLOCKED, "Planilha pedia bloqueio, mas o AD ja estava bloqueado"),
        (TYPE_UNBLOCK_ALREADY_RELEASED, "Planilha pedia desbloqueio, mas o AD ja estava liberado"),
    )

    source_module = models.CharField(max_length=40, choices=SOURCE_CHOICES, default=SOURCE_BLOCK_OPERATIONAL)
    divergence_type = models.CharField(max_length=60, choices=DIVERGENCE_TYPE_CHOICES)
    dedupe_key = models.CharField(max_length=255, unique=True)
    collaborator_id = models.PositiveIntegerField(db_index=True)
    collaborator_name = models.CharField(max_length=255)
    usuario_ad = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    system_name = models.CharField(max_length=150, default="AD PRIN")
    initial_action = models.CharField(max_length=20, blank=True)
    sheet_status = models.CharField(max_length=50, blank=True)
    real_status = models.CharField(max_length=50, blank=True)
    internal_status_after_sync = models.CharField(max_length=50, blank=True)
    data_saida = models.DateField(null=True, blank=True)
    data_retorno = models.DateField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "notification_divergence_audits"
        ordering = ["-created_at"]
        verbose_name = "Auditoria de divergencia"
        verbose_name_plural = "Auditorias de divergencia"

    def __str__(self) -> str:
        return f"{self.collaborator_name} - {self.divergence_type}"
