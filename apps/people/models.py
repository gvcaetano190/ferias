from django.db import models


class Colaborador(models.Model):
    nome = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    login_ad = models.CharField(max_length=150, blank=True, null=True)
    departamento = models.CharField(max_length=255, blank=True, null=True)
    gestor = models.CharField(max_length=255, blank=True, null=True)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "colaboradores"
        ordering = ["nome"]
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores"

    def __str__(self) -> str:
        return self.nome


class Ferias(models.Model):
    colaborador = models.ForeignKey(
        Colaborador,
        models.DO_NOTHING,
        db_column="colaborador_id",
        related_name="ferias_registros",
    )
    data_saida = models.DateField(blank=True, null=True)
    data_retorno = models.DateField(blank=True, null=True)
    mes_ref = models.IntegerField(blank=True, null=True)
    ano_ref = models.IntegerField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "ferias"
        ordering = ["-ano_ref", "-mes_ref", "-data_saida"]
        verbose_name = "Evento de férias"
        verbose_name_plural = "Eventos de férias"

    def __str__(self) -> str:
        return f"{self.colaborador} - {self.data_saida}"


class Acesso(models.Model):
    colaborador = models.ForeignKey(
        Colaborador,
        models.DO_NOTHING,
        db_column="colaborador_id",
        related_name="acessos_registros",
    )
    sistema = models.CharField(max_length=150)
    status = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "acessos"
        ordering = ["colaborador__nome", "sistema"]
        verbose_name = "Acesso"
        verbose_name_plural = "Acessos"

    def __str__(self) -> str:
        return f"{self.colaborador} - {self.sistema}"


class SyncLog(models.Model):
    tipo_sync = models.CharField(max_length=100)
    status = models.CharField(max_length=30)
    total_registros = models.IntegerField(blank=True, null=True)
    total_abas = models.IntegerField(blank=True, null=True)
    mensagem = models.TextField(blank=True, null=True)
    arquivo_hash = models.CharField(max_length=64, blank=True, null=True)
    detalhes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "sync_logs"
        ordering = ["-created_at"]
        verbose_name = "Log de sincronização"
        verbose_name_plural = "Logs de sincronização"

    def __str__(self) -> str:
        return f"{self.tipo_sync} - {self.status}"
