from django.db import models


class BlockConfig(models.Model):
    nome = models.CharField(max_length=120, default="Configuração principal")
    usuario_teste_ad = models.CharField(max_length=150, blank=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "block_configs"
        ordering = ["-ativo", "nome"]
        verbose_name = "Configuração Block"
        verbose_name_plural = "Configurações Block"

    def __str__(self) -> str:
        return f"{self.nome} ({'ativa' if self.ativo else 'inativa'})"


class BlockProcessing(models.Model):
    colaborador_id = models.IntegerField(db_index=True)
    usuario_ad = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    acao = models.CharField(max_length=20)
    ad_status = models.CharField(max_length=50, blank=True)
    vpn_status = models.CharField(max_length=50, blank=True)
    resultado = models.CharField(max_length=20)
    mensagem = models.TextField(blank=True)
    executado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "block_processings"
        ordering = ["-executado_em"]
        verbose_name = "Processamento Block"
        verbose_name_plural = "Processamentos Block"

    def __str__(self) -> str:
        return f"{self.usuario_ad or self.colaborador_id} - {self.acao} - {self.resultado}"
