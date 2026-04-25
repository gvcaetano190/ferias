from django.db import models


class BlockConfig(models.Model):
    nome = models.CharField(max_length=120, default="Configuração principal")
    usuario_teste_ad = models.CharField(max_length=150, blank=True)
    ativo = models.BooleanField(default=True)
    dry_run = models.BooleanField(default=False)
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
    data_saida = models.DateField(blank=True, null=True)
    data_retorno = models.DateField(blank=True, null=True)
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


class BlockVerificationRun(models.Model):
    STATUS_SUCCESS = "SUCCESS"
    STATUS_ERROR = "ERROR"

    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default=STATUS_SUCCESS)
    total_inicial_bloqueio = models.PositiveIntegerField(default=0)
    total_inicial_desbloqueio = models.PositiveIntegerField(default=0)
    total_final_bloqueio = models.PositiveIntegerField(default=0)
    total_final_desbloqueio = models.PositiveIntegerField(default=0)
    total_sincronizados = models.PositiveIntegerField(default=0)
    total_ignorados = models.PositiveIntegerField(default=0)
    total_erros = models.PositiveIntegerField(default=0)
    summary_message = models.TextField(blank=True)

    class Meta:
        db_table = "block_verification_runs"
        ordering = ["-started_at"]
        verbose_name = "Verificação operacional do block"
        verbose_name_plural = "Verificações operacionais do block"

    def __str__(self) -> str:
        return f"Verificacao block - {self.started_at:%d/%m/%Y %H:%M:%S}"


class BlockVerificationItem(models.Model):
    ACTION_BLOCK = "BLOQUEAR"
    ACTION_UNLOCK = "DESBLOQUEAR"
    ACTION_IGNORE = "IGNORAR"
    ACTION_CHOICES = (
        (ACTION_BLOCK, "Bloquear"),
        (ACTION_UNLOCK, "Desbloquear"),
        (ACTION_IGNORE, "Ignorar"),
    )

    OUTCOME_KEPT = "MANTIDO"
    OUTCOME_REMOVED = "REMOVIDO_DA_FILA"
    OUTCOME_SYNCED = "SINCRONIZADO"
    OUTCOME_ERROR = "ERRO_VERIFICACAO"
    OUTCOME_CHOICES = (
        (OUTCOME_KEPT, "Mantido"),
        (OUTCOME_REMOVED, "Removido da fila"),
        (OUTCOME_SYNCED, "Sincronizado"),
        (OUTCOME_ERROR, "Erro de verificacao"),
    )

    run = models.ForeignKey(BlockVerificationRun, on_delete=models.CASCADE, related_name="items")
    colaborador_id = models.IntegerField(db_index=True)
    colaborador_nome = models.CharField(max_length=255)
    usuario_ad = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    data_saida = models.DateField(blank=True, null=True)
    data_retorno = models.DateField(blank=True, null=True)
    acao_inicial = models.CharField(max_length=20, choices=ACTION_CHOICES)
    acao_final = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resultado_verificacao = models.CharField(max_length=30, choices=OUTCOME_CHOICES)
    ad_status_banco_antes = models.CharField(max_length=50, blank=True)
    vpn_status_banco_antes = models.CharField(max_length=50, blank=True)
    ad_status_real = models.CharField(max_length=50, blank=True)
    vpn_status_real = models.CharField(max_length=50, blank=True)
    ad_status_banco_depois = models.CharField(max_length=50, blank=True)
    vpn_status_banco_depois = models.CharField(max_length=50, blank=True)
    motivo = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "block_verification_items"
        ordering = ["run_id", "colaborador_nome", "usuario_ad"]
        verbose_name = "Item da verificação block"
        verbose_name_plural = "Itens da verificação block"

    def __str__(self) -> str:
        return f"{self.colaborador_nome} - {self.acao_inicial} -> {self.acao_final}"
