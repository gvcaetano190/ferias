from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.shared.repositories.people import ColaboradorRepository, FeriasRepository
from apps.shared.repositories.sync import SyncLogRepository


MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


@dataclass
class DashboardPeriod:
    year: int
    month: int

    @property
    def key(self) -> str:
        return f"{self.year}-{self.month:02d}"

    @property
    def label(self) -> str:
        return f"{MESES_PT.get(self.month, self.month)} {self.year}"


class DashboardService:
    def __init__(self):
        self.colaboradores = ColaboradorRepository()
        self.ferias = FeriasRepository()
        self.sync_logs = SyncLogRepository()

    def available_periods(self) -> list[DashboardPeriod]:
        return [
            DashboardPeriod(year=item["ano_ref"], month=item["mes_ref"])
            for item in self.ferias.periods()
        ]

    def resolve_period(self, value: str | None) -> DashboardPeriod | None:
        periods = self.available_periods()
        if not periods:
            return None
        if value:
            for period in periods:
                if period.key == value:
                    return period
        today = timezone.localdate()
        for period in periods:
            if period.year == today.year and period.month == today.month:
                return period
        return periods[0]

    def summary(self, period: DashboardPeriod | None) -> dict:
        today = timezone.localdate()
        latest_sync = self.sync_logs.latest()
        active_people = self.colaboradores.active_count()

        if not period:
            return {
                "latest_sync": latest_sync,
                "active_people": active_people,
                "periods": [],
                "selected_period": None,
                "metrics": {},
                "rows": [],
            }

        base = self.ferias.by_period(period.year, period.month)

        next_returns = [today + timedelta(days=1)]
        if today.weekday() == 4:
            next_returns = [today + timedelta(days=offset) for offset in (1, 2, 3)]

        rows = [
            {
                "nome": item.colaborador.nome,
                "motivo": "FÉRIAS",
                "saida": item.data_saida,
                "retorno": item.data_retorno,
                "gestor": item.colaborador.gestor,
                "departamento": item.colaborador.departamento,
            }
            for item in base.order_by("data_saida", "colaborador__nome")
        ]

        metrics = {
            "saindo_hoje": base.filter(data_saida=today).count(),
            "voltando": base.filter(data_retorno__in=next_returns).count(),
            "em_ferias": base.filter(data_saida__lte=today, data_retorno__gte=today).count(),
            "proximos_7_dias": base.filter(
                data_saida__gt=today,
                data_saida__lte=today + timedelta(days=7),
            ).count(),
            "total_periodo": base.count(),
        }
        return {
            "latest_sync": latest_sync,
            "active_people": active_people,
            "periods": self.available_periods(),
            "selected_period": period,
            "metrics": metrics,
            "rows": rows,
        }
