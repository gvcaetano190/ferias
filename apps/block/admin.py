from django.contrib import admin

from apps.block.models import BlockConfig, BlockProcessing, BlockVerificationItem, BlockVerificationRun


@admin.register(BlockConfig)
class BlockConfigAdmin(admin.ModelAdmin):
    list_display = ("nome", "usuario_teste_ad", "dry_run", "ativo", "updated_at")
    list_filter = ("ativo", "dry_run")
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


class BlockVerificationItemInline(admin.TabularInline):
    model = BlockVerificationItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "colaborador_nome",
        "usuario_ad",
        "acao_inicial",
        "acao_final",
        "resultado_verificacao",
        "ad_status_banco_antes",
        "ad_status_real",
        "ad_status_banco_depois",
        "motivo",
        "created_at",
    )


@admin.register(BlockVerificationRun)
class BlockVerificationRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "status",
        "total_inicial_bloqueio",
        "total_inicial_desbloqueio",
        "total_final_bloqueio",
        "total_final_desbloqueio",
        "total_sincronizados",
        "total_erros",
    )
    list_filter = ("status",)
    search_fields = ("summary_message",)
    readonly_fields = (
        "started_at",
        "finished_at",
        "status",
        "total_inicial_bloqueio",
        "total_inicial_desbloqueio",
        "total_final_bloqueio",
        "total_final_desbloqueio",
        "total_sincronizados",
        "total_ignorados",
        "total_erros",
        "summary_message",
    )
    inlines = [BlockVerificationItemInline]


@admin.register(BlockVerificationItem)
class BlockVerificationItemAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "colaborador_nome",
        "usuario_ad",
        "acao_inicial",
        "acao_final",
        "resultado_verificacao",
    )
    list_filter = ("acao_inicial", "acao_final", "resultado_verificacao")
    search_fields = ("colaborador_nome", "usuario_ad", "motivo")
    readonly_fields = (
        "created_at",
        "run",
        "colaborador_nome",
        "usuario_ad",
        "email",
        "acao_inicial",
        "acao_final",
        "resultado_verificacao",
        "ad_status_banco_antes",
        "vpn_status_banco_antes",
        "ad_status_real",
        "vpn_status_real",
        "ad_status_banco_depois",
        "vpn_status_banco_depois",
        "motivo",
    )
