from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from apps.accesses.repositories import AccessesRepository


RETURNED_BLOCKED_STATUSES = {"BLOQUEADO", "BLOQUEADA"}
ACTIVE_DURING_VACATION_STATUSES = {"ATIVO", "LIBERADO"}
PENDING_DURING_VACATION_STATUSES = {"NB"}
BLOCKABLE_AD_STATUSES = {"", "LIBERADO", "NB", "NP"}
UNLOCKABLE_AD_STATUSES = {"BLOQUEADO", "BLOQUEADA"}
BLOCK_SCOPE_OUT = "FORA"
BLOCK_SCOPE_BLOCK = "BLOQUEAR"
BLOCK_SCOPE_UNLOCK = "DESBLOQUEAR"
SITUATION_LABELS = {
    "BLOQUEADO": "Bloqueado",
    "LIBERADO": "Liberado",
    "PENDENTE": "Pendente",
    "NORMAL": "Férias em breve",
}


@dataclass(frozen=True)
class AccessesFilters:
    referencia: str = ""
    query: str = ""
    sistema: str = ""
    status: str = ""
    gestor: str = ""
    situacao: str = ""


class AccessesService:
    def __init__(self, repository: AccessesRepository | None = None) -> None:
        self.repository = repository or AccessesRepository()

    def resolve_filters(self, params) -> AccessesFilters:
        today = timezone.localdate()
        return AccessesFilters(
            referencia=(params.get("referencia") or f"{today.year:04d}-{today.month:02d}").strip(),
            query=(params.get("q") or "").strip(),
            sistema=(params.get("sistema") or "").strip(),
            status=(params.get("status") or "").strip(),
            gestor=(params.get("gestor") or "").strip(),
            situacao=(params.get("situacao") or "").strip(),
        )

    def dashboard_data(self, filters: AccessesFilters) -> dict:
        rows = self._build_rows(filters)
        systems = self.repository.listar_sistemas()
        filtered_rows = [row for row in rows if self._matches_filters_raw(row, filters)]
        table_rows = self._build_table_rows(filtered_rows, systems)
        table_rows = [row for row in table_rows if self._matches_filters_grouped(row, filters)]
        return {
            "filters": filters,
            "resumo": self._build_summary(table_rows, systems),
            "rows": table_rows,
            "referencias": self._build_reference_options(rows),
            "sistemas": systems,
            "system_headers": [
                {"value": system, "label": self._format_system_label(system)}
                for system in systems
            ],
            "statuses": self.repository.listar_statuses(),
            "gestores": self.repository.listar_gestores(),
            "situacoes": [
                ("BLOQUEADO", "Bloqueados"),
                ("LIBERADO", "Liberados"),
                ("PENDENTE", "Pendências de acesso"),
                ("NORMAL", "Férias em breve"),
            ],
        }

    def _build_rows(self, filters: AccessesFilters) -> list[dict]:
        today = timezone.localdate()
        ref_year, ref_month = self._parse_reference(filters.referencia)
        ferias_map = self.repository.obter_ferias_por_referencia(ano=ref_year, mes=ref_month)
        collaborator_ids = sorted(ferias_map.keys())
        access_items = list(self.repository.listar_acessos_por_colaboradores(collaborator_ids))
        processing_map = self.repository.obter_ultimos_processamentos_block(collaborator_ids)
        rows: list[dict] = []

        for item in access_items:
            ferias = ferias_map.get(item.colaborador_id)
            last_processing = processing_map.get(item.colaborador_id)
            referencia, reference_date = self._build_reference(ferias)
            rows.append(
                {
                    "colaborador_id": item.colaborador_id,
                    "colaborador": item.colaborador.nome,
                    "email": item.colaborador.email,
                    "usuario_ad": item.colaborador.login_ad,
                    "gestor": item.colaborador.gestor,
                    "departamento": item.colaborador.departamento,
                    "sistema": item.sistema,
                    "status": item.status or "-",
                    "motivo": "Férias" if ferias else "-",
                    "data_saida": getattr(ferias, "data_saida", None),
                    "data_retorno": getattr(ferias, "data_retorno", None),
                    "referencia": referencia,
                    "reference_date": reference_date,
                    "mes_ref": getattr(ferias, "mes_ref", None),
                    "ano_ref": getattr(ferias, "ano_ref", None),
                    "ferias_ativa": bool(
                        ferias
                        and ferias.data_saida
                        and ferias.data_retorno
                        and ferias.data_saida <= today < ferias.data_retorno
                    ),
                    "retorno_vigente": bool(ferias and ferias.data_retorno and ferias.data_retorno <= today),
                    "ultima_acao_block": getattr(last_processing, "acao", ""),
                    "ultimo_resultado_block": getattr(last_processing, "resultado", ""),
                    "ultimo_status_ad": getattr(last_processing, "ad_status", ""),
                    "ultimo_status_vpn": getattr(last_processing, "vpn_status", ""),
                    "ultimo_processamento_em": getattr(last_processing, "executado_em", None),
                }
            )

        return rows

    def _matches_filters_raw(self, row: dict, filters: AccessesFilters) -> bool:
        if filters.referencia and row["referencia"] != filters.referencia:
            return False

        if filters.query:
            haystack = " ".join(
                str(value or "")
                for value in [
                    row["colaborador"],
                    row["email"],
                    row["usuario_ad"],
                    row["sistema"],
                    row["gestor"],
                    row["departamento"],
                ]
            ).lower()
            if filters.query.lower() not in haystack:
                return False

        if filters.sistema and row["sistema"] != filters.sistema:
            return False
        if filters.status and row["status"] != filters.status:
            return False
        if filters.gestor and (row["gestor"] or "") != filters.gestor:
            return False
        return True

    def _matches_filters_grouped(self, row: dict, filters: AccessesFilters) -> bool:
        if filters.query:
            haystack = " ".join(
                str(value or "")
                for value in [
                    row["colaborador"],
                    row["email"],
                    row["gestor"],
                ]
            ).lower()
            if filters.query.lower() not in haystack:
                return False

        if filters.gestor and (row["gestor"] or "") != filters.gestor:
            return False

        if filters.situacao and row["situacao"] != filters.situacao:
            return False

        if filters.status:
            normalized_filter = filters.status.strip().upper()
            valid_statuses = {
                (value or "").strip().upper()
                for value in row["systems"].values()
                if (value or "").strip()
            }
            if normalized_filter not in valid_statuses:
                return False

        return True

    def _build_reference_options(self, rows: list[dict]) -> list[dict]:
        options_map: dict[str, dict] = {}
        for row in rows:
            key = row["referencia"]
            if not key:
                continue
            if key not in options_map:
                options_map[key] = {
                    "value": key,
                    "label": self._format_reference_label(row["reference_date"]),
                }
        return sorted(options_map.values(), key=lambda item: item["value"], reverse=True)

    def _build_summary(self, rows: list[dict], systems: list[str]) -> dict[str, int]:
        return {
            "colaboradores_monitorados": len(rows),
            "sistemas_monitorados": len(systems),
            "bloqueados": sum(1 for row in rows if row["situacao"] == "BLOQUEADO"),
            "retornados_bloqueados": sum(1 for row in rows if row["situacao"] == "BLOQUEADO" and row.get("retorno_vigente")),
            "pendencias": sum(1 for row in rows if row["situacao"] == "PENDENTE"),
            "fila_block": sum(1 for row in rows if row["block_scope"] in {BLOCK_SCOPE_BLOCK, BLOCK_SCOPE_UNLOCK}),
            "pendencias_fora_block": sum(
                1 for row in rows if row["situacao"] == "PENDENTE" and row["block_scope"] == BLOCK_SCOPE_OUT
            ),
        }

    def _build_table_rows(self, rows: list[dict], systems: list[str]) -> list[dict]:
        today = timezone.localdate()
        grouped: dict[int, dict] = {}
        for row in rows:
            item = grouped.setdefault(
                row["colaborador_id"],
                {
                    "colaborador_id": row["colaborador_id"],
                    "colaborador": row["colaborador"],
                    "email": row["email"],
                    "usuario_ad": row["usuario_ad"],
                    "gestor": row["gestor"],
                    "departamento": row["departamento"],
                    "motivo": row["motivo"],
                    "data_saida": row["data_saida"],
                    "data_retorno": row["data_retorno"],
                    "ferias_ativa": row["ferias_ativa"],
                    "retorno_vigente": row["retorno_vigente"],
                    "ultima_acao_block": row["ultima_acao_block"],
                    "ultimo_resultado_block": row["ultimo_resultado_block"],
                    "ultimo_status_ad": row["ultimo_status_ad"],
                    "ultimo_status_vpn": row["ultimo_status_vpn"],
                    "ultimo_processamento_em": row["ultimo_processamento_em"],
                    "systems": {system: "-" for system in systems},
                    "system_cells": ["-" for _ in systems],
                },
            )
            item["systems"][row["sistema"]] = row["status"]
        result = sorted(grouped.values(), key=lambda item: item["colaborador"])
        for item in result:
            item["system_cells"] = [item["systems"].get(system, "-") for system in systems]
            item["situacao"] = self._classify_collaborator(item["systems"], item["ferias_ativa"], item["retorno_vigente"])
            item["situacao_label"] = SITUATION_LABELS[item["situacao"]]
            item["block_scope"], item["block_scope_reason"] = self._classify_block_scope(item, today=today)
        return result

    def _classify_block_scope(self, item: dict, *, today: date) -> tuple[str, str]:
        ad_status = (item["systems"].get("AD PRIN") or "").strip().upper()
        data_saida = item.get("data_saida")
        data_retorno = item.get("data_retorno")

        if data_saida and data_retorno and data_saida <= today < data_retorno and ad_status in BLOCKABLE_AD_STATUSES:
            return BLOCK_SCOPE_BLOCK, "Em férias com AD ainda liberado ou indefinido."

        if data_retorno and data_retorno <= today and ad_status in UNLOCKABLE_AD_STATUSES:
            return BLOCK_SCOPE_UNLOCK, "Já retornou e o AD ainda está bloqueado."

        if item["situacao"] == "PENDENTE":
            return BLOCK_SCOPE_OUT, "Pendência geral em outros sistemas; o block não precisa agir no AD."

        return BLOCK_SCOPE_OUT, "AD já está coerente com a regra de férias."

    def _classify_collaborator(self, systems: dict[str, str], ferias_ativa: bool, retorno_vigente: bool) -> str:
        effective_statuses = []
        for value in systems.values():
            normalized = (value or "").strip().upper()
            if normalized in {"", "-", "NP"}:
                continue
            effective_statuses.append(normalized)

        has_liberado = any(status in ACTIVE_DURING_VACATION_STATUSES for status in effective_statuses)
        has_bloqueado = any(status in RETURNED_BLOCKED_STATUSES for status in effective_statuses)

        if has_liberado and has_bloqueado:
            return "PENDENTE"

        if retorno_vigente and has_bloqueado:
            return "PENDENTE"

        if has_bloqueado:
            return "BLOQUEADO"

        if has_liberado:
            return "LIBERADO"

        return "NORMAL"

    def _build_reference(self, ferias) -> tuple[str, date | None]:
        if not ferias:
            return "", None

        if ferias.ano_ref and ferias.mes_ref:
            ref_date = date(ferias.ano_ref, ferias.mes_ref, 1)
            return f"{ferias.ano_ref:04d}-{ferias.mes_ref:02d}", ref_date

        fallback_date = ferias.data_saida or ferias.data_retorno
        if fallback_date:
            return f"{fallback_date.year:04d}-{fallback_date.month:02d}", fallback_date.replace(day=1)
        return "", None

    def _parse_reference(self, value: str) -> tuple[int, int]:
        year_str, month_str = value.split("-", 1)
        return int(year_str), int(month_str)

    def _format_reference_label(self, value: date | None) -> str:
        if not value:
            return "Sem referência"
        months = [
            "",
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        return f"{months[value.month]} {value.year}"

    def _format_system_label(self, system: str) -> str:
        if system == "AD PRIN":
            return "AD"
        return system
