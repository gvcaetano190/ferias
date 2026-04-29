from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.utils import timezone

from apps.block.models import BlockVerificationItem
from apps.block.repositories import BlockRepository


class BlockPreviewService:
    def __init__(self):
        self.repository = BlockRepository()

    def previsualizar_verificacao_block(self) -> dict:
        preview_rows: list[dict] = []

        seen_collaborators: set[int] = set()
        for ferias in self.repository.buscar_para_bloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            row = self._preview_usuario_bloqueio(ferias)
            if row:
                preview_rows.append(row)

        seen_collaborators = set()
        for ferias in self.repository.buscar_para_desbloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            row = self._preview_usuario_desbloqueio(ferias)
            if row:
                preview_rows.append(row)

        preview_rows.sort(
            key=lambda item: (
                item["acao_ordem"],
                item["data_referencia"] or timezone.localdate(),
                item["colaborador"],
            )
        )

        return {
            "rows": preview_rows,
            "summary": {
                "bloquear": sum(1 for item in preview_rows if item["acao_prevista"] == "BLOQUEAR"),
                "desbloquear": sum(1 for item in preview_rows if item["acao_prevista"] == "DESBLOQUEAR"),
                "ignorar": sum(1 for item in preview_rows if item["acao_prevista"] == "IGNORAR"),
                "total": len(preview_rows),
            },
        }

    def _preview_usuario_bloqueio(self, ferias) -> dict | None:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        vpn_status_atual = self.repository.obter_status_vpn(collaborator.id)
        totvs_status_atual = self.repository.obter_status_totvs(collaborator.id)
        force_operational_check = self._should_force_operational_check(
            ad_status_atual,
            vpn_status_atual,
        )
        ja_processado = self.repository.ja_processado_hoje(collaborator.id, "BLOQUEIO")
        motivo = (
            "Saindo de ferias hoje"
            if ferias.data_saida == timezone.localdate()
            else "Em ferias e ainda nao bloqueado"
        )
        if ja_processado:
            return None
        if not self.repository.pode_bloquear(collaborator.id) and not force_operational_check:
            return None
        return self._preview_row(
            ferias,
            acao_ordem=0,
            ad_status_atual=ad_status_atual,
            vpn_status_atual=vpn_status_atual,
            totvs_status_atual=totvs_status_atual,
            acao_prevista="BLOQUEAR",
            motivo=self._decorate_force_operational_reason(
                motivo,
                force_operational_check=force_operational_check,
                force_totvs_operational_check=False,
            ),
            force_operational_check=force_operational_check,
        )

    def _preview_usuario_desbloqueio(self, ferias) -> dict | None:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        vpn_status_atual = self.repository.obter_status_vpn(collaborator.id)
        totvs_status_atual = self.repository.obter_status_totvs(collaborator.id)
        force_operational_check = self._should_force_operational_check(
            ad_status_atual,
            vpn_status_atual,
        )
        ja_processado = self.repository.ja_processado_hoje(collaborator.id, "DESBLOQUEIO")
        motivo = (
            "Retornando de ferias hoje"
            if ferias.data_retorno == timezone.localdate()
            else "Ja retornou e ainda esta bloqueado"
        )
        if ja_processado:
            return None
        if not self.repository.pode_desbloquear(collaborator.id) and not force_operational_check:
            return None
        return self._preview_row(
            ferias,
            acao_ordem=1,
            ad_status_atual=ad_status_atual,
            vpn_status_atual=vpn_status_atual,
            totvs_status_atual=totvs_status_atual,
            acao_prevista="DESBLOQUEAR",
            motivo=self._decorate_force_operational_reason(
                motivo,
                force_operational_check=force_operational_check,
                force_totvs_operational_check=False,
            ),
            force_operational_check=force_operational_check,
        )

    def _preview_row(
        self,
        ferias,
        *,
        acao_ordem: int,
        ad_status_atual: str,
        vpn_status_atual: str,
        totvs_status_atual: str,
        acao_prevista: str,
        motivo: str,
        force_operational_check: bool,
    ) -> dict:
        collaborator = ferias.colaborador
        return {
            "colaborador": collaborator.nome,
            "email": collaborator.email or "-",
            "usuario_ad": collaborator.login_ad or "-",
            "acao_ordem": acao_ordem,
            "data_saida": ferias.data_saida,
            "data_retorno": ferias.data_retorno,
            "data_referencia": ferias.data_saida if acao_ordem == 0 else ferias.data_retorno,
            "status_atual_ad": ad_status_atual or "-",
            "status_atual_vpn": vpn_status_atual or "-",
            "status_atual_totvs": totvs_status_atual or "-",
            "acao_prevista": acao_prevista,
            "motivo": motivo,
            "force_operational_check": force_operational_check,
        }

    def _should_force_operational_check(self, ad_status: str, vpn_status: str) -> bool:
        ad_value = (ad_status or "").strip().upper()
        vpn_value = (vpn_status or "").strip().upper()
        return ad_value == "NP" and vpn_value == "NP"

    def _should_force_totvs_operational_check(self, totvs_status: str) -> bool:
        value = (totvs_status or "").strip().upper()
        return value in {"NB", "NP"}

    def _decorate_force_operational_reason(
        self,
        motivo: str,
        *,
        force_operational_check: bool,
        force_totvs_operational_check: bool,
    ) -> str:
        extras = []
        if force_operational_check:
            extras.append("AD e VPN estao como NP no banco")
        if force_totvs_operational_check:
            extras.append("TOTVS esta como NB/NP no banco")
        if not extras:
            return motivo
        return f"{motivo} Validacao forcada porque {' e '.join(extras)}."

    def ver_detalhes_verificacao_operacional(self, *, run_id: int | None = None) -> dict:
        run = self.repository.buscar_verificacao_operacional_run(run_id)

        if not run:
            return {
                "run": None,
                "summary": None,
                "lista_inicial": [],
                "lista_final": [],
                "lista_removida": [],
                "lista_sincronizada": [],
                "queue_is_source_for_next_job": False,
            }

        items = list(run.items.all())
        lista_final = [item for item in items if item.acao_final in {"BLOQUEAR", "DESBLOQUEAR"}]
        lista_removida = [
            item
            for item in items
            if item.acao_final == "IGNORAR" and item.resultado_verificacao == BlockVerificationItem.OUTCOME_REMOVED
        ]
        lista_sincronizada = [
            item
            for item in items
            if item.resultado_verificacao in {BlockVerificationItem.OUTCOME_SYNCED, BlockVerificationItem.OUTCOME_ERROR}
        ]
        lista_diferenca = lista_removida + lista_sincronizada
        final_bloquear = [item for item in lista_final if item.acao_final == "BLOQUEAR"]
        final_desbloquear = [item for item in lista_final if item.acao_final == "DESBLOQUEAR"]
        diferenca_sincronizados = [
            item for item in lista_diferenca if item.resultado_verificacao == BlockVerificationItem.OUTCOME_SYNCED
        ]
        diferenca_erros = [
            item for item in lista_diferenca if item.resultado_verificacao == BlockVerificationItem.OUTCOME_ERROR
        ]
        diferenca_removidos = [
            item for item in lista_diferenca if item.resultado_verificacao == BlockVerificationItem.OUTCOME_REMOVED
        ]
        return {
            "run": run,
            "summary": {
                "inicial_total": len(items),
                "final_total": len(lista_final),
                "final_bloquear": len(final_bloquear),
                "final_desbloquear": len(final_desbloquear),
                "removida_total": len(lista_removida),
                "sincronizada_total": len(lista_sincronizada),
                "diferenca_total": len(lista_diferenca),
                "diferenca_sincronizados": len(diferenca_sincronizados),
                "diferenca_erros": len(diferenca_erros),
                "diferenca_removidos": len(diferenca_removidos),
            },
            "lista_inicial": items,
            "lista_final": lista_final,
            "lista_final_bloquear": final_bloquear,
            "lista_final_desbloquear": final_desbloquear,
            "lista_removida": lista_removida,
            "lista_sincronizada": lista_sincronizada,
            "lista_diferenca": lista_diferenca,
            "queue_is_source_for_next_job": self.repository.buscar_verificacao_operacional_run_pronta_hoje(
                run_id=run.id
            )
            is not None,
        }

    def dashboard_data(self) -> dict:
        today = timezone.localdate()
        config = self.repository.obter_configuracao_ativa_block()
        latest_verification_run = self.repository.buscar_verificacao_operacional_run()
        return {
            "resumo": self.repository.resumo_dashboard_block(
                return_year=today.year,
                return_month=today.month,
            ),
            "ultimos_processamentos": self.repository.listar_processamentos(
                limit=50,
                return_year=today.year,
                return_month=today.month,
            ),
            "configuracao_ativa": config,
            "usuario_teste_atual": self.repository.obter_usuario_teste_block(),
            "dry_run": bool(config and config.dry_run),
            "filtros": {
                "reference": f"{today.year:04d}-{today.month:02d}",
            },
            "sync_cache": self._sync_cache_info(),
            "referencias_retorno": self._referencias_retorno(),
            "ultimas_verificacoes": list(self.repository.buscar_verificacao_operacional_run()._meta.model.objects.all()[:5])
            if latest_verification_run
            else [],
            "itens_ultima_verificacao": list(latest_verification_run.items.all()[:20]) if latest_verification_run else [],
            "ultima_verificacao": latest_verification_run,
        }

    def dashboard_data_filtrada(self, *, reference=None) -> dict:
        today = timezone.localdate()
        reference = reference or f"{today.year:04d}-{today.month:02d}"
        return_year, return_month = self._parse_reference(reference)
        config = self.repository.obter_configuracao_ativa_block()
        latest_verification_run = self.repository.buscar_verificacao_operacional_run()

        from apps.block.models import BlockVerificationRun

        return {
            "resumo": self.repository.resumo_dashboard_block(
                return_year=return_year,
                return_month=return_month,
            ),
            "ultimos_processamentos": self.repository.listar_processamentos(
                limit=50,
                return_year=return_year,
                return_month=return_month,
            ),
            "configuracao_ativa": config,
            "usuario_teste_atual": self.repository.obter_usuario_teste_block(),
            "dry_run": bool(config and config.dry_run),
            "filtros": {
                "reference": f"{return_year:04d}-{return_month:02d}",
            },
            "sync_cache": self._sync_cache_info(),
            "referencias_retorno": self._referencias_retorno(),
            "ultimas_verificacoes": list(BlockVerificationRun.objects.all()[:5]),
            "itens_ultima_verificacao": list(latest_verification_run.items.all()[:20]) if latest_verification_run else [],
            "ultima_verificacao": latest_verification_run,
        }

    def _parse_reference(self, reference: str | None) -> tuple[int, int]:
        today = timezone.localdate()
        if not reference:
            return today.year, today.month
        try:
            year_str, month_str = reference.split("-", 1)
            year = int(year_str)
            month = int(month_str)
            if 1 <= month <= 12:
                return year, month
        except (TypeError, ValueError):
            pass
        return today.year, today.month

    def _referencias_retorno(self) -> list[dict]:
        labels = [
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
        return [
            {
                "value": f"{year:04d}-{month:02d}",
                "label": f"{labels[month - 1]} {year}",
            }
            for year, month in self.repository.listar_referencias_retorno(limit=12)
        ]

    def _sync_cache_info(self) -> dict:
        from apps.core.models import OperationalSettings

        operational_settings = OperationalSettings.get_solo()
        cache_window = int(operational_settings.cache_minutes or 0)
        cached_files = sorted(
            settings.DOWNLOAD_DIR.glob("planilha_*.xlsx"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        if not cached_files:
            return {
                "configured_minutes": cache_window,
                "has_cache": False,
                "status": "Sem cache local",
                "detail": "A próxima sincronização precisará baixar a planilha novamente.",
            }

        latest = cached_files[0]
        age_minutes = max(0, int((datetime.now().timestamp() - latest.stat().st_mtime) / 60))
        remaining_minutes = max(0, cache_window - age_minutes)
        is_valid = remaining_minutes > 0
        return {
            "configured_minutes": cache_window,
            "has_cache": True,
            "is_valid": is_valid,
            "status": "Cache ativo" if is_valid else "Cache expirado",
            "detail": (
                f"Arquivo local baixado há {age_minutes} min. "
                f"{remaining_minutes} min restantes para buscar uma nova planilha automaticamente."
                if is_valid
                else "O cache local expirou. A próxima sincronização buscará uma nova planilha."
            ),
            "file_name": latest.name,
            "age_minutes": age_minutes,
            "remaining_minutes": remaining_minutes,
            "last_download_at": datetime.fromtimestamp(
                latest.stat().st_mtime,
                tz=timezone.get_current_timezone(),
            ),
        }
