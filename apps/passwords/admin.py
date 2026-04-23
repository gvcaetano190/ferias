from django.contrib import admin

from apps.passwords.models import PasswordLink


@admin.register(PasswordLink)
class PasswordLinkAdmin(admin.ModelAdmin):
    list_display = ("nome_pessoa", "finalidade", "usuario_criador", "visualizado", "criado_em", "expirado_em")
    list_filter = ("visualizado", "finalidade")
    search_fields = ("nome_pessoa", "gestor_pessoa", "descricao", "secret_key")
    readonly_fields = ("secret_key", "link_url", "metadata_key", "criado_em")
