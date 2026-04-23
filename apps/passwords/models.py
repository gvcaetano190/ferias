from django.db import models


class PasswordLink(models.Model):
    senha_usada = models.CharField(max_length=255, blank=True, null=True)
    secret_key = models.CharField(max_length=255, unique=True)
    link_url = models.URLField(unique=True)
    ttl_seconds = models.IntegerField()
    metadata_key = models.CharField(max_length=255, blank=True, null=True)
    nome_pessoa = models.CharField(max_length=255, blank=True, null=True)
    gestor_pessoa = models.CharField(max_length=255, blank=True, null=True)
    descricao = models.TextField(blank=True, null=True)
    finalidade = models.CharField(max_length=255, blank=True, null=True)
    usuario_criador = models.CharField(max_length=255, blank=True, null=True)
    visualizado = models.BooleanField(default=False)
    criado_em = models.DateTimeField(blank=True, null=True)
    expirado_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "password_links"
        ordering = ["-criado_em"]
        verbose_name = "Link de senha"
        verbose_name_plural = "Links de senha"

    def __str__(self) -> str:
        return self.nome_pessoa or self.secret_key
