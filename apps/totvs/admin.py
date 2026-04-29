from __future__ import annotations

from django.contrib import admin

from apps.totvs.credentials import TotvsCredentialStore
from apps.totvs.forms import TotvsIntegrationConfigAdminForm
from apps.totvs.models import TotvsIntegrationConfig


@admin.register(TotvsIntegrationConfig)
class TotvsIntegrationConfigAdmin(admin.ModelAdmin):
    form = TotvsIntegrationConfigAdminForm
    list_display = (
        "name",
        "base_url",
        "tenant_id",
        "active",
        "credential_status",
        "last_test_status",
        "last_tested_at",
    )
    list_filter = ("active", "auth_type", "verify_ssl", "last_test_status")
    search_fields = ("name", "base_url", "tenant_id", "credential_key")
    readonly_fields = (
        "credential_key",
        "credential_status",
        "last_tested_at",
        "last_test_status",
        "last_test_message",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Conexao",
            {
                "fields": (
                    "name",
                    "active",
                    "base_url",
                    "tenant_id",
                    "auth_type",
                    "timeout_seconds",
                    "verify_ssl",
                )
            },
        ),
        (
            "Credencial segura",
            {
                "fields": (
                    "credential_key",
                    "credential_status",
                    "credential_username",
                    "credential_password",
                )
            },
        ),
        (
            "Diagnostico",
            {
                "fields": (
                    "last_tested_at",
                    "last_test_status",
                    "last_test_message",
                )
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def credential_status(self, obj: TotvsIntegrationConfig) -> str:
        if not obj.credential_key:
            return "Sem credencial cadastrada"
        stored = TotvsCredentialStore().exists(credential_key=obj.credential_key)
        return "Credencial armazenada no cofre" if stored else "Referencia sem credencial no cofre"

    credential_status.short_description = "Status da credencial"

