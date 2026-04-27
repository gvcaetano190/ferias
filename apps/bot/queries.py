"""
BotQueryService
===============
Consultas ao banco de dados disparadas pelos comandos do bot WhatsApp.
"""
from __future__ import annotations

from datetime import date


class BotQueryService:

    def saidas_hoje(self) -> list[dict]:
        """Retorna quem começa férias hoje."""
        from apps.people.models import Ferias
        hoje = date.today()
        qs = Ferias.objects.filter(data_saida=hoje).select_related("colaborador")
        return [
            {"nome": f.colaborador.nome, "setor": f.colaborador.departamento or "—"}
            for f in qs
        ]

    def retornos_hoje(self) -> list[dict]:
        """Retorna quem volta de férias hoje."""
        from apps.people.models import Ferias
        hoje = date.today()
        qs = Ferias.objects.filter(data_retorno=hoje).select_related("colaborador")
        return [
            {"nome": f.colaborador.nome, "setor": f.colaborador.departamento or "—"}
            for f in qs
        ]

    def ausentes_agora(self) -> list[dict]:
        """Retorna quem está de férias agora (saiu e ainda não voltou)."""
        from apps.people.models import Ferias
        hoje = date.today()
        qs = (
            Ferias.objects
            .filter(data_saida__lte=hoje, data_retorno__gte=hoje)
            .select_related("colaborador")
        )
        return [
            {"nome": f.colaborador.nome, "setor": f.colaborador.departamento or "—"}
            for f in qs
        ]

    def resumo_mes(self, month: int, year: int) -> dict:
        """Resumo de saídas, retornos e ainda ausentes no mês."""
        from apps.reports.services import ReportService
        service = ReportService()
        summary = service.get_period_summary(month=month, year=year)
        return summary
