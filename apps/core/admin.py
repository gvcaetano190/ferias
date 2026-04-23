from django.contrib import admin

from apps.core.models import OperationalSettings


@admin.register(OperationalSettings)
class OperationalSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Geral", {"fields": ("company_name",)}),
        ("Sincronização", {"fields": ("google_sheets_url", "sync_enabled", "cache_minutes", "allowed_systems")}),
        ("OneTimeSecret", {"fields": ("onetimesecret_enabled", "onetimesecret_email", "onetimesecret_api_key")}),
        ("Auditoria", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return not OperationalSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
