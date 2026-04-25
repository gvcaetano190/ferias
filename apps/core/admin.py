from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from apps.core.models import OperationalSettings
from apps.scheduler.app_control import ApplicationControlService


@admin.register(OperationalSettings)
class OperationalSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Configuracoes gerais", {"fields": ("company_name",)}),
        ("Aplicacao e servicos", {"fields": ("auto_start_scheduler_with_server",)}),
        ("Sincronizacao", {"fields": ("google_sheets_url", "sync_enabled", "cache_minutes", "allowed_systems")}),
        ("OneTimeSecret", {"fields": ("onetimesecret_enabled", "onetimesecret_email", "onetimesecret_api_key")}),
        ("Auditoria", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")
    change_form_template = "admin/core/operationalsettings/change_form.html"

    def has_add_permission(self, request):
        return not OperationalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/restart-application/",
                self.admin_site.admin_view(self.restart_application_view),
                name="core_operationalsettings_restart_application",
            ),
        ]
        return custom_urls + urls

    def restart_application_view(self, request, object_id):
        settings = self.get_object(request, object_id)
        if settings is None:
            self.message_user(request, "Configuracao operacional nao encontrada.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:core_operationalsettings_changelist"))

        if request.method == "POST":
            ok, message = ApplicationControlService().restart_web_application()
            self.message_user(
                request,
                message,
                level=messages.SUCCESS if ok else messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:core_operationalsettings_change", args=[settings.pk])
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": settings,
            "title": "Reiniciar aplicacao",
        }
        return TemplateResponse(
            request,
            "admin/core/operationalsettings/restart_application.html",
            context,
        )
