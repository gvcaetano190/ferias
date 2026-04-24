from __future__ import annotations

from datetime import date

from django.db.models import Count, Q
from django.utils import timezone

from apps.block.models import BlockConfig, BlockProcessing
from apps.people.models import Acesso, Colaborador, Ferias


class BlockRepository:
    AD_SYSTEM_NAME = "AD PRIN"
    VPN_SYSTEM_NAME = "VPN"
    BLOCKABLE_AD_STATUSES = {"", "LIBERADO", "NB", "NP"}
    UNLOCKABLE_AD_STATUSES = {"BLOQUEADO", "BLOQUEADA"}

    def _janela_operacional_inicio(self) -> date:
        today = timezone.localdate()
        month = today.month - 1
        year = today.year
        if month == 0:
            month = 12
            year -= 1
        # Mantemos só o mês atual e o mês anterior para evitar reprocessar férias antigas.
        return date(year, month, 1)

    def buscar_para_bloqueio_hoje(self):
        today = timezone.localdate()
        window_start = self._janela_operacional_inicio()
        return (
            Ferias.objects.select_related("colaborador")
            .filter(data_saida=today)
            .filter(Q(data_saida__gte=window_start) | Q(data_retorno__gte=window_start))
            .exclude(colaborador__login_ad__isnull=True)
            .exclude(colaborador__login_ad__exact="")
            .order_by("colaborador__nome")
        )

    def buscar_para_desbloqueio_hoje(self):
        today = timezone.localdate()
        window_start = self._janela_operacional_inicio()
        return (
            Ferias.objects.select_related("colaborador")
            .filter(data_retorno=today)
            .filter(data_retorno__gte=window_start)
            .exclude(colaborador__login_ad__isnull=True)
            .exclude(colaborador__login_ad__exact="")
            .order_by("colaborador__nome")
        )

    def obter_status_ad(self, colaborador_id: int) -> str:
        acesso = (
            Acesso.objects.filter(colaborador_id=colaborador_id, sistema=self.AD_SYSTEM_NAME)
            .order_by("-updated_at", "-id")
            .first()
        )
        return (getattr(acesso, "status", "") or "").strip().upper()

    def pode_bloquear(self, colaborador_id: int) -> bool:
        return self.obter_status_ad(colaborador_id) in self.BLOCKABLE_AD_STATUSES

    def pode_desbloquear(self, colaborador_id: int) -> bool:
        return self.obter_status_ad(colaborador_id) in self.UNLOCKABLE_AD_STATUSES

    def obter_configuracao_ativa_block(self) -> BlockConfig | None:
        return BlockConfig.objects.filter(ativo=True).order_by("-updated_at").first()

    def obter_usuario_teste_block(self) -> str | None:
        config = self.obter_configuracao_ativa_block()
        if config and config.usuario_teste_ad.strip():
            return config.usuario_teste_ad.strip()
        return None

    def ja_processado_hoje(self, colaborador_id: int, acao: str) -> bool:
        today = timezone.localdate()
        return BlockProcessing.objects.filter(
            colaborador_id=colaborador_id,
            acao=acao,
            resultado="SUCESSO",
            executado_em__date=today,
        ).exists()

    def atualizar_status_block(
        self,
        *,
        colaborador_id: int,
        ad_status: str,
        vpn_status: str | None = None,
    ) -> None:
        # AD e VPN usam a mesma tabela de acessos por sistema.
        Acesso.objects.update_or_create(
            colaborador_id=colaborador_id,
            sistema=self.AD_SYSTEM_NAME,
            defaults={"status": ad_status},
        )
        if vpn_status is not None:
            Acesso.objects.update_or_create(
                colaborador_id=colaborador_id,
                sistema=self.VPN_SYSTEM_NAME,
                defaults={"status": vpn_status},
            )

    def salvar_resultado_execucao(
        self,
        *,
        colaborador_id: int,
        usuario_ad: str,
        email: str,
        acao: str,
        data_saida=None,
        data_retorno=None,
        ad_status: str,
        vpn_status: str,
        resultado: str,
        mensagem: str,
    ) -> BlockProcessing:
        return BlockProcessing.objects.create(
            colaborador_id=colaborador_id,
            usuario_ad=usuario_ad,
            email=email,
            acao=acao,
            data_saida=data_saida,
            data_retorno=data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=mensagem,
        )

    def listar_ultimos_processamentos(self, limit: int = 20):
        today = timezone.localdate()
        return self.listar_processamentos(limit=limit, return_year=today.year, return_month=today.month)

    def listar_processamentos(self, *, limit: int = 50, return_year=None, return_month=None):
        ferias_qs = Ferias.objects.all()
        if return_year and return_month:
            ferias_qs = ferias_qs.filter(data_retorno__year=return_year, data_retorno__month=return_month)

        collaborator_ids = list(ferias_qs.values_list("colaborador_id", flat=True).distinct())
        ferias_list = list(
            Ferias.objects.filter(colaborador_id__in=collaborator_ids)
            .select_related("colaborador")
            .order_by("colaborador_id", "-data_retorno", "-data_saida")
        )
        ferias_map = {}
        for item in ferias_list:
            ferias_map.setdefault(item.colaborador_id, []).append(item)

        processings = list(
            BlockProcessing.objects.filter(colaborador_id__in=collaborator_ids)
            .order_by("-executado_em")[:limit]
        )
        processings = self._deduplicar_processamentos(processings)
        collaborator_map = {
            item.id: item.nome
            for item in Colaborador.objects.filter(id__in=collaborator_ids)
        }
        rows = []
        for processing in processings:
            ferias = self._resolver_ferias_para_processamento(
                processing,
                ferias_map.get(processing.colaborador_id, []),
                return_year=return_year,
                return_month=return_month,
            )
            data_saida = processing.data_saida or getattr(ferias, "data_saida", None)
            data_retorno = processing.data_retorno or getattr(ferias, "data_retorno", None)
            if return_year and return_month and data_retorno:
                if data_retorno.year != return_year or data_retorno.month != return_month:
                    continue
            rows.append(
                {
                    "colaborador": collaborator_map.get(processing.colaborador_id, "Desconhecido"),
                    "email": processing.email,
                    "usuario_ad": processing.usuario_ad,
                    "data_saida": data_saida,
                    "data_retorno": data_retorno,
                    "acao_executada": processing.acao,
                    "status_ad": processing.ad_status,
                    "status_vpn": processing.vpn_status,
                    "resultado": processing.resultado,
                    "mensagem": processing.mensagem,
                    "executado_em": processing.executado_em,
                }
            )
        return rows

    def _deduplicar_processamentos(self, processings):
        unicos = []
        vistos = set()
        for processing in processings:
            chave = (
                processing.colaborador_id,
                processing.usuario_ad,
                processing.acao,
                processing.ad_status,
                processing.vpn_status,
                processing.resultado,
                processing.mensagem,
                timezone.localtime(processing.executado_em).date(),
            )
            if chave in vistos:
                continue
            vistos.add(chave)
            unicos.append(processing)
        return unicos

    def _resolver_ferias_para_processamento(self, processing, ferias_items, *, return_year=None, return_month=None):
        if processing.data_saida or processing.data_retorno:
            return type(
                "FeriasRef",
                (),
                {
                    "data_saida": processing.data_saida,
                    "data_retorno": processing.data_retorno,
                },
            )()

        if not ferias_items:
            return None

        execution_date = timezone.localtime(processing.executado_em).date()
        elegiveis = [item for item in ferias_items if item.data_retorno <= execution_date]
        if elegiveis:
            return sorted(elegiveis, key=lambda item: (item.data_retorno, item.data_saida), reverse=True)[0]

        return ferias_items[0]

    def resumo_dashboard_block(self, *, return_year=None, return_month=None) -> dict[str, int]:
        ferias_qs = Ferias.objects.all()
        if return_year and return_month:
            ferias_qs = ferias_qs.filter(data_retorno__year=return_year, data_retorno__month=return_month)
        collaborator_ids = list(ferias_qs.values_list("colaborador_id", flat=True).distinct())
        processings = BlockProcessing.objects.filter(colaborador_id__in=collaborator_ids)
        grouped = (
            processings
            .values("resultado", "acao")
            .annotate(total=Count("id"))
        )
        summary = {
            "bloqueados_periodo": 0,
            "desbloqueados_periodo": 0,
            "erros_periodo": 0,
            "ignorados_periodo": 0,
        }
        for item in grouped:
            if item["resultado"] == "SUCESSO" and item["acao"] == "BLOQUEIO":
                summary["bloqueados_periodo"] += item["total"]
            elif item["resultado"] == "SUCESSO" and item["acao"] == "DESBLOQUEIO":
                summary["desbloqueados_periodo"] += item["total"]
            elif item["resultado"] == "ERRO":
                summary["erros_periodo"] += item["total"]
            elif item["resultado"] == "IGNORADO":
                summary["ignorados_periodo"] += item["total"]
        return summary

    def listar_referencias_retorno(self, *, limit: int = 12):
        referencias = []
        vistos = set()
        for item in Ferias.objects.exclude(data_retorno__isnull=True).order_by("-data_retorno").values_list(
            "data_retorno", flat=True
        ):
            chave = (item.year, item.month)
            if chave in vistos:
                continue
            vistos.add(chave)
            referencias.append(chave)
            if len(referencias) >= limit:
                break
        return referencias
