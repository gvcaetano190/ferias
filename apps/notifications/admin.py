from __future__ import annotations

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.notifications.models import (
    NotificationDelivery,
    NotificationDivergenceAudit,
    NotificationProviderConfig,
    NotificationTarget,
)
from apps.notifications.services import NotificationService


class NotificationProviderTestForm(forms.Form):
    target = forms.ModelChoiceField(
        queryset=NotificationTarget.objects.filter(enabled=True).order_by("name"),
        required=False,
        label="Destino para teste",
        help_text="Se vazio, usa o destino padrao configurado no provider.",
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6, "cols": 80}),
        required=False,
        label="Mensagem de teste",
    )


@admin.register(NotificationTarget)
class NotificationTargetAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "target_type", "destination", "enabled", "is_default", "updated_at")
    list_filter = ("enabled", "channel", "target_type", "is_default")
    search_fields = ("name", "destination", "description")
    fieldsets = (
        ("Identificacao", {"fields": ("name", "description")}),
        ("Destino", {"fields": ("channel", "target_type", "destination")}),
        ("Estado", {"fields": ("enabled", "is_default")}),
        ("Auditoria", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(NotificationProviderConfig)
class NotificationProviderConfigAdmin(admin.ModelAdmin):
    list_display = ("name", "provider_type", "enabled", "default_target", "timeout_seconds", "updated_at")
    list_filter = ("enabled", "provider_type")
    search_fields = ("name", "endpoint_url")
    change_form_template = "admin/notifications/notificationproviderconfig/change_form.html"
    fieldsets = (
        ("Provider", {"fields": ("name", "provider_type", "enabled")}),
        ("Evolution API (WhatsApp)", {"fields": ("endpoint_url", "api_key", "timeout_seconds", "default_target")}),
        ("Auditoria", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/test-message/",
                self.admin_site.admin_view(self.test_message_view),
                name="notifications_notificationproviderconfig_test_message",
            ),
        ]
        return custom_urls + urls

    def test_message_view(self, request, object_id):
        provider = self.get_object(request, object_id)
        if provider is None:
            self.message_user(request, "Provider de notificacao nao encontrado.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:notifications_notificationproviderconfig_changelist"))

        initial_message = (
            "Teste de notificacao do Controle de Ferias.\n\n"
            "Se esta mensagem chegou, a configuracao da Evolution API e do destino esta funcionando."
        )
        form = NotificationProviderTestForm(request.POST or None, initial={"message": initial_message})
        if request.method == "POST" and form.is_valid():
            target = form.cleaned_data["target"]
            message_text = (form.cleaned_data["message"] or initial_message).strip()
            try:
                delivery = NotificationService().send_test_message(
                    provider_config=provider,
                    text=message_text,
                    target=target,
                )
            except Exception as exc:
                self.message_user(request, f"Falha ao enviar teste: {exc}", level=messages.ERROR)
            else:
                if delivery.status == NotificationDelivery.STATUS_SENT:
                    self.message_user(request, "Mensagem de teste enviada com sucesso.", level=messages.SUCCESS)
                else:
                    self.message_user(
                        request,
                        f"Falha ao enviar teste: {delivery.error_message or 'Erro desconhecido.'}",
                        level=messages.ERROR,
                    )
                return HttpResponseRedirect(
                    reverse("admin:notifications_notificationproviderconfig_change", args=[provider.pk])
                )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": provider,
            "title": "Testar envio de notificacao",
            "form": form,
        }
        return TemplateResponse(
            request,
            "admin/notifications/notificationproviderconfig/test_message.html",
            context,
        )


@admin.register(NotificationDelivery)
class NotificationDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event_key", "provider", "target", "status", "sent_at")
    list_filter = ("status", "provider__provider_type", "created_at")
    search_fields = ("event_key", "destination_snapshot", "message_preview", "error_message")
    readonly_fields = (
        "event_key",
        "dedupe_key",
        "provider",
        "target",
        "destination_snapshot",
        "message_preview",
        "status",
        "provider_response",
        "error_message",
        "sent_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(NotificationDivergenceAudit)
class NotificationDivergenceAuditAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "collaborator_name",
        "usuario_ad",
        "system_name",
        "divergence_type",
        "real_status",
        "notified_at",
    )
    list_filter = ("source_module", "divergence_type", "system_name", "notified_at", "created_at")
    search_fields = ("collaborator_name", "usuario_ad", "email", "dedupe_key")
    readonly_fields = (
        "source_module",
        "divergence_type",
        "dedupe_key",
        "collaborator_id",
        "collaborator_name",
        "usuario_ad",
        "email",
        "system_name",
        "initial_action",
        "sheet_status",
        "real_status",
        "internal_status_after_sync",
        "data_saida",
        "data_retorno",
        "details",
        "notified_at",
        "resolved_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
