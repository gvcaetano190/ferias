from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import groupby

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
    STATUS_ALL = "all"
    STATUS_SAIDA_HOJE = "saida_hoje"
    STATUS_PROXIMO_SAIR = "proximo_sair"
    STATUS_EM_FERIAS = "em_ferias"
    STATUS_RETORNOU = "retornou"
    STATUS_PROXIMO_RETORNO = "proximo_retorno"

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

    def available_statuses(self) -> list[dict[str, str]]:
        return [
            {"key": self.STATUS_ALL, "label": "Todos"},
            {"key": self.STATUS_SAIDA_HOJE, "label": "Saídas hoje"},
            {"key": self.STATUS_PROXIMO_SAIR, "label": "Próximo a sair"},
            {"key": self.STATUS_EM_FERIAS, "label": "Em férias"},
            {"key": self.STATUS_RETORNOU, "label": "Retornou"},
            {"key": self.STATUS_PROXIMO_RETORNO, "label": "Próximo a retornar"},
        ]

    def resolve_status(self, value: str | None) -> str:
        available = {item["key"] for item in self.available_statuses()}
        return value if value in available else self.STATUS_ALL

    def resolve_return_date(self, value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    def row_status(self, item, today):
        if item.data_saida and item.data_saida == today:
            return self.STATUS_SAIDA_HOJE, "Saída hoje"
        if item.data_saida and today < item.data_saida <= today + timedelta(days=7):
            return self.STATUS_PROXIMO_SAIR, "Próximo a sair"
        if item.data_retorno and today < item.data_retorno <= today + timedelta(days=7):
            return self.STATUS_PROXIMO_RETORNO, "Próximo a retornar"
        if item.data_retorno and item.data_retorno < today:
            return self.STATUS_RETORNOU, "Retornou"
        if item.data_saida and item.data_retorno and item.data_saida <= today <= item.data_retorno:
            return self.STATUS_EM_FERIAS, "Em férias"
        return self.STATUS_ALL, "Fora do status"

    def matches_status(self, item, selected_status: str, today) -> bool:
        if selected_status == self.STATUS_ALL:
            return True
        if selected_status == self.STATUS_SAIDA_HOJE:
            return bool(item.data_saida and item.data_saida == today)
        if selected_status == self.STATUS_PROXIMO_SAIR:
            return bool(item.data_saida and today < item.data_saida <= today + timedelta(days=7))
        if selected_status == self.STATUS_EM_FERIAS:
            return bool(item.data_saida and item.data_retorno and item.data_saida <= today <= item.data_retorno)
        if selected_status == self.STATUS_RETORNOU:
            return bool(item.data_retorno and item.data_retorno < today)
        if selected_status == self.STATUS_PROXIMO_RETORNO:
            return bool(item.data_retorno and today < item.data_retorno <= today + timedelta(days=7))
        return False

    def summary(self, period: DashboardPeriod | None, status: str | None = None, return_date: str | None = None) -> dict:
        today = timezone.localdate()
        latest_sync = self.sync_logs.latest()
        active_people = self.colaboradores.active_count()
        selected_status = self.resolve_status(status)
        selected_return_date = self.resolve_return_date(return_date)

        if not period:
            return {
                "latest_sync": latest_sync,
                "active_people": active_people,
                "periods": [],
                "selected_period": None,
                "status_options": self.available_statuses(),
                "selected_status": selected_status,
                "selected_return_date": selected_return_date,
                "metrics": {},
                "rows": [],
            }

        base = self.ferias.by_period(period.year, period.month)

        next_returns = [today + timedelta(days=1)]
        if today.weekday() == 4:
            next_returns = [today + timedelta(days=offset) for offset in (1, 2, 3)]

        rows = []
        for item in base.order_by("data_retorno", "data_saida", "colaborador__nome"):
            status_key, status_label = self.row_status(item, today)
            row = {
                "nome": item.colaborador.nome,
                "motivo": "FÉRIAS",
                "saida": item.data_saida,
                "retorno": item.data_retorno,
                "gestor": item.colaborador.gestor,
                "departamento": item.colaborador.departamento,
                "status_key": status_key,
                "status_label": status_label,
            }
            if selected_return_date and item.data_retorno != selected_return_date:
                continue
            if self.matches_status(item, selected_status, today):
                rows.append(row)

        grouped_rows = []
        for retorno, items in groupby(rows, key=lambda row: row["retorno"]):
            grouped_rows.append(
                {
                    "retorno": retorno,
                    "label": retorno.strftime("%d/%m/%Y") if retorno else "Sem data de retorno",
                    "rows": list(items),
                }
            )

        metrics = {
            "saindo_hoje": base.filter(data_saida=today).count(),
            "voltando": base.filter(data_retorno__in=next_returns).count(),
            "em_ferias": base.filter(data_saida__lte=today, data_retorno__gte=today).count(),
            "proximos_7_dias": base.filter(
                data_retorno__gt=today,
                data_retorno__lte=today + timedelta(days=7),
            ).count(),
            "retornaram": base.filter(data_retorno__lt=today).count(),
            "total_periodo": base.count(),
        }
        return {
            "latest_sync": latest_sync,
            "active_people": active_people,
            "periods": self.available_periods(),
            "selected_period": period,
            "status_options": self.available_statuses(),
            "selected_status": selected_status,
            "selected_return_date": selected_return_date,
            "metrics": metrics,
            "rows": rows,
            "grouped_rows": grouped_rows,
        }
