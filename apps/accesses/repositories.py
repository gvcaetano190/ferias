from __future__ import annotations

from apps.block.models import BlockProcessing
from apps.people.models import Acesso, Colaborador, Ferias


CANONICAL_SYSTEM_ORDER = ["AD PRIN", "VPN", "Gmail", "Admin", "Metrics", "TOTVS"]


class AccessesRepository:
    def listar_colaboradores_por_referencia(self, *, ano: int, mes: int):
        collaborator_ids = (
            Ferias.objects.filter(ano_ref=ano, mes_ref=mes)
            .values_list("colaborador_id", flat=True)
            .distinct()
        )
        return Colaborador.objects.filter(id__in=collaborator_ids).order_by("nome")

    def listar_acessos(self):
        return (
            Acesso.objects.select_related("colaborador")
            .exclude(colaborador__isnull=True)
            .order_by("colaborador__nome", "sistema")
        )

    def listar_acessos_por_colaboradores(self, collaborator_ids: list[int]):
        return (
            Acesso.objects.select_related("colaborador")
            .filter(colaborador_id__in=collaborator_ids)
            .order_by("colaborador__nome", "sistema")
        )

    def listar_sistemas(self) -> list[str]:
        available = set(Acesso.objects.values_list("sistema", flat=True).distinct())
        ordered = [system for system in CANONICAL_SYSTEM_ORDER if system in available]
        extras = sorted(available.difference(CANONICAL_SYSTEM_ORDER))
        return ordered + extras

    def listar_statuses(self) -> list[str]:
        statuses = (
            Acesso.objects.exclude(status__isnull=True)
            .exclude(status__exact="")
            .order_by("status")
            .values_list("status", flat=True)
            .distinct()
        )
        return list(statuses)

    def listar_gestores(self) -> list[str]:
        return list(
            Acesso.objects.exclude(colaborador__gestor__isnull=True)
            .exclude(colaborador__gestor__exact="")
            .order_by("colaborador__gestor")
            .values_list("colaborador__gestor", flat=True)
            .distinct()
        )

    def obter_ferias_recentes(self, colaborador_ids: list[int]) -> dict[int, Ferias]:
        ferias_map: dict[int, Ferias] = {}
        queryset = (
            Ferias.objects.filter(colaborador_id__in=colaborador_ids)
            .order_by("colaborador_id", "-data_saida", "-data_retorno", "-id")
        )
        for item in queryset:
            ferias_map.setdefault(item.colaborador_id, item)
        return ferias_map

    def obter_ferias_por_referencia(self, *, ano: int, mes: int) -> dict[int, Ferias]:
        ferias_map: dict[int, Ferias] = {}
        queryset = (
            Ferias.objects.filter(ano_ref=ano, mes_ref=mes)
            .order_by("colaborador_id", "-data_saida", "-data_retorno", "-id")
        )
        for item in queryset:
            ferias_map.setdefault(item.colaborador_id, item)
        return ferias_map

    def obter_ultimos_processamentos_block(self, colaborador_ids: list[int]) -> dict[int, BlockProcessing]:
        processing_map: dict[int, BlockProcessing] = {}
        queryset = BlockProcessing.objects.filter(colaborador_id__in=colaborador_ids).order_by(
            "colaborador_id",
            "-executado_em",
            "-id",
        )
        for item in queryset:
            processing_map.setdefault(item.colaborador_id, item)
        return processing_map
