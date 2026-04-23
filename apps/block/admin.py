from django.contrib import admin

from apps.block.models import BlockConfig, BlockProcessing


@admin.register(BlockConfig)
class BlockConfigAdmin(admin.ModelAdmin):
    list_display = ("nome", "usuario_teste_ad", "ativo", "updated_at")
    list_filter = ("ativo",)
    search_fields = ("nome", "usuario_teste_ad")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.ativo:
            BlockConfig.objects.exclude(pk=obj.pk).update(ativo=False)


@admin.register(BlockProcessing)
class BlockProcessingAdmin(admin.ModelAdmin):
    list_display = (
        "executado_em",
        "colaborador_id",
        "usuario_ad",
        "acao",
        "resultado",
        "ad_status",
        "vpn_status",
    )
    list_filter = ("acao", "resultado", "ad_status", "vpn_status")
    search_fields = ("usuario_ad", "email", "mensagem")
    readonly_fields = ("executado_em",)
