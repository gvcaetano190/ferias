from __future__ import annotations

import uuid

from django.db import models


class TotvsIntegrationConfig(models.Model):
    AUTH_BASIC = "basic"
    AUTH_CHOICES = (
        (AUTH_BASIC, "Basic Auth"),
    )

    TEST_STATUS_SUCCESS = "SUCCESS"
    TEST_STATUS_ERROR = "ERROR"
    TEST_STATUS_CHOICES = (
        (TEST_STATUS_SUCCESS, "Sucesso"),
        (TEST_STATUS_ERROR, "Erro"),
    )

    name = models.CharField(max_length=120, default="TOTVS principal")
    base_url = models.URLField(
        default="https://fmimpressos170648.protheus.cloudtotvs.com.br:2007",
        help_text="Informe apenas a base do ambiente. Ex.: https://host:porta",
    )
    tenant_id = models.CharField(max_length=40, default="01,01")
    auth_type = models.CharField(max_length=20, choices=AUTH_CHOICES, default=AUTH_BASIC)
    credential_key = models.CharField(
        max_length=120,
        unique=True,
        blank=True,
        help_text="Referencia interna da credencial guardada no cofre do sistema.",
    )
    timeout_seconds = models.PositiveIntegerField(default=30)
    verify_ssl = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    last_tested_at = models.DateTimeField(blank=True, null=True)
    last_test_status = models.CharField(max_length=20, choices=TEST_STATUS_CHOICES, blank=True)
    last_test_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "totvs_integration_configs"
        ordering = ["-active", "name"]
        verbose_name = "Configuracao TOTVS"
        verbose_name_plural = "Configuracoes TOTVS"

    def save(self, *args, **kwargs):
        if not self.credential_key:
            self.credential_key = f"totvs-{uuid.uuid4().hex}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({'ativa' if self.active else 'inativa'})"

