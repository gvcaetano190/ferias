from django.contrib import admin

from apps.people.models import Acesso, Colaborador, Ferias, SyncLog


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    list_display = ("nome", "email", "departamento", "gestor", "ativo")
    list_filter = ("ativo", "departamento")
    search_fields = ("nome", "email", "login_ad", "gestor")


@admin.register(Ferias)
class FeriasAdmin(admin.ModelAdmin):
    list_display = ("colaborador", "data_saida", "data_retorno", "mes_ref", "ano_ref")
    list_filter = ("ano_ref", "mes_ref")
    search_fields = ("colaborador__nome", "colaborador__email")


@admin.register(Acesso)
class AcessoAdmin(admin.ModelAdmin):
    list_display = ("colaborador", "sistema", "status", "updated_at")
    list_filter = ("sistema", "status")
    search_fields = ("colaborador__nome", "colaborador__email", "sistema")


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("tipo_sync", "status", "total_registros", "total_abas", "created_at")
    list_filter = ("tipo_sync", "status")
    search_fields = ("mensagem", "arquivo_hash", "detalhes")
    readonly_fields = ("created_at",)
