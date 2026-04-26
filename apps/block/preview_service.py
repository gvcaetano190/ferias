from __future__ import annotations

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
        ja_processado = self.repository.ja_processado_hoje(collaborator.id, "BLOQUEIO")
        motivo = (
            "Saindo de férias hoje"
            if ferias.data_saida == timezone.localdate()
            else "Em férias e ainda não bloqueado"
        )
        if ja_processado:
            return self._preview_row(
                ferias,
                acao_ordem=0,
                ad_status_atual=ad_status_atual,
                vpn_status_atual=vpn_status_atual,
                acao_prevista="IGNORAR",
                motivo="Já processado hoje com sucesso",
            )
        if not self.repository.pode_bloquear(collaborator.id):
            return None
        return self._preview_row(
            ferias,
            acao_ordem=0,
            ad_status_atual=ad_status_atual,
            vpn_status_atual=vpn_status_atual,
            acao_prevista="BLOQUEAR",
            motivo=motivo,
        )

    def _preview_usuario_desbloqueio(self, ferias) -> dict | None:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        vpn_status_atual = self.repository.obter_status_vpn(collaborator.id)
        ja_processado = self.repository.ja_processado_hoje(collaborator.id, "DESBLOQUEIO")
        motivo = (
            "Retornando de férias hoje"
            if ferias.data_retorno == timezone.localdate()
            else "Já retornou e ainda está bloqueado"
        )
        if ja_processado:
            return self._preview_row(
                ferias,
                acao_ordem=1,
                ad_status_atual=ad_status_atual,
                vpn_status_atual=vpn_status_atual,
                acao_prevista="IGNORAR",
                motivo="Já processado hoje com sucesso",
            )
        if not self.repository.pode_desbloquear(collaborator.id):
            return None
        return self._preview_row(
            ferias,
            acao_ordem=1,
            ad_status_atual=ad_status_atual,
            vpn_status_atual=vpn_status_atual,
            acao_prevista="DESBLOQUEAR",
            motivo=motivo,
        )

    def _preview_row(
        self,
        ferias,
        *,
        acao_ordem: int,
        ad_status_atual: str,
        vpn_status_atual: str,
        acao_prevista: str,
        motivo: str,
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
            "acao_prevista": acao_prevista,
            "motivo": motivo,
        }

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
            item for item in items
            if item.acao_final == "IGNORAR" and item.resultado_verificacao == BlockVerificationItem.OUTCOME_REMOVED
        ]
        lista_sincronizada = [
            item for item in items
            if item.resultado_verificacao in {BlockVerificationItem.OUTCOME_SYNCED, BlockVerificationItem.OUTCOME_ERROR}
        ]
        return {
            "run": run,
            "summary": {
                "inicial_total": len(items),
                "final_total": len(lista_final),
                "removida_total": len(lista_removida),
                "sincronizada_total": len(lista_sincronizada),
            },
            "lista_inicial": items,
            "lista_final": lista_final,
            "lista_removida": lista_removida,
            "lista_sincronizada": lista_sincronizada,
            "queue_is_source_for_next_job": self.repository.buscar_verificacao_operacional_run_pronta_hoje(run_id=run.id) is not None,
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
            "referencias_retorno": self._referencias_retorno(),
            "ultimas_verificacoes": list(self.repository.buscar_verificacao_operacional_run()._meta.model.objects.all()[:5]) if latest_verification_run else [],
            "itens_ultima_verificacao": list(latest_verification_run.items.all()[:20]) if latest_verification_run else [],
            "ultima_verificacao": latest_verification_run,
        }

    def dashboard_data_filtrada(self, *, reference=None) -> dict:
        today = timezone.localdate()
        reference = reference or f"{today.year:04d}-{today.month:02d}"
        return_year, return_month = self._parse_reference(reference)
        config = self.repository.obter_configuracao_ativa_block()
        latest_verification_run = self.repository.buscar_verificacao_operacional_run()
        
        # fix the queryset to get last runs correctly without using private API if possible
        # since I need the queryset:
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
