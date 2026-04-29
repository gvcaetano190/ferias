from __future__ import annotations

import logging
from dataclasses import dataclass
from types import SimpleNamespace

from django.utils import timezone

from apps.block.models import BlockVerificationItem, BlockVerificationRun
from apps.block.preview_service import BlockPreviewService
from apps.block.repositories import BlockRepository
from apps.notifications.services import NotificationService
from apps.totvs.services import TotvsIntegrationService
from integrations.ad.executor import (
    bloquear_usuario_ad,
    bloquear_usuarios_ad,
    consultar_usuario_ad,
    consultar_usuarios_ad,
    desbloquear_usuario_ad,
    desbloquear_usuarios_ad,
)

logger = logging.getLogger(__name__)


@dataclass
class BlockServiceResult:
    bloqueios_feitos: int = 0
    desbloqueios_feitos: int = 0
    sincronizados: int = 0
    erros: int = 0
    ignorados: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "bloqueios_feitos": self.bloqueios_feitos,
            "desbloqueios_feitos": self.desbloqueios_feitos,
            "sincronizados": self.sincronizados,
            "erros": self.erros,
            "ignorados": self.ignorados,
        }


class BlockBusinessService:
    def __init__(self):
        self.repository = BlockRepository()
        self.preview_service = BlockPreviewService()
        self.notification_service = NotificationService()
        self.totvs_service = TotvsIntegrationService()

    def processar_verificacao_block(self, *, require_operational_queue: bool = False, notify: bool = True) -> dict:
        config = self.repository.obter_configuracao_ativa_block()
        dry_run = bool(config and config.dry_run)
        result = BlockServiceResult()
        verification_run = self.repository.buscar_verificacao_operacional_run_pronta_hoje()
        if require_operational_queue and not verification_run:
            payload = result.as_dict()
            payload["dry_run"] = dry_run
            payload["verification_run_id"] = None
            payload["used_operational_queue"] = False
            payload["skipped"] = True
            payload["message"] = (
                "Verificacao block aguardando uma verificacao operacional concluida hoje para usar a fila final."
            )
            if notify:
                self._notify_block_execution_status(payload)
            return payload
        try:
            if verification_run:
                result = self._processar_fila_verificacao_operacional(
                    verification_run,
                    result=result,
                    dry_run=dry_run,
                )
            else:
                result = self.processar_bloqueios(result, dry_run=dry_run)
                result = self.processar_desbloqueios(result, dry_run=dry_run)
            payload = result.as_dict()
            payload["dry_run"] = dry_run
            payload["verification_run_id"] = verification_run.id if verification_run else None
            payload["used_operational_queue"] = bool(verification_run)
            payload["message"] = self._build_block_execution_summary_message(payload)
            if notify:
                self._notify_block_execution_status(payload)
            return payload
        except Exception as exc:
            payload = result.as_dict()
            payload["dry_run"] = dry_run
            payload["verification_run_id"] = verification_run.id if verification_run else None
            payload["used_operational_queue"] = bool(verification_run)
            payload["message"] = str(exc)
            payload["status"] = "error"
            if notify:
                self._notify_block_execution_status(payload)
            raise

    def processar_verificacao_operacional_block(self, *, notify: bool = True) -> dict:
        run = self.repository.criar_verificacao_operacional_run(status=BlockVerificationRun.STATUS_SUCCESS)
        summary = {
            "run_id": run.id,
            "total_inicial_bloqueio": 0,
            "total_inicial_desbloqueio": 0,
            "total_final_bloqueio": 0,
            "total_final_desbloqueio": 0,
            "total_sincronizados": 0,
            "total_ignorados": 0,
            "total_erros": 0,
        }

        try:
            items = self._build_verification_candidates()
            ad_lookup = self._consultar_estados_ad_operacionais(items)
            totvs_lookup = self._consultar_estados_totvs_operacionais(items)
            summary["total_inicial_bloqueio"] = sum(1 for item in items if item["acao_inicial"] == "BLOQUEAR")
            summary["total_inicial_desbloqueio"] = sum(1 for item in items if item["acao_inicial"] == "DESBLOQUEAR")

            for item in items:
                processed = self._process_verification_candidate(
                    item,
                    ad_lookup=ad_lookup,
                    totvs_lookup=totvs_lookup,
                )
                processed.pop("motivo_inicial", None)
                processed.pop("force_operational_check", None)
                processed.pop("force_totvs_operational_check", None)
                self.repository.criar_verificacao_item(run=run, **processed)
                if processed["acao_final"] == "BLOQUEAR":
                    summary["total_final_bloqueio"] += 1
                elif processed["acao_final"] == "DESBLOQUEAR":
                    summary["total_final_desbloqueio"] += 1

                if processed["resultado_verificacao"] == BlockVerificationItem.OUTCOME_SYNCED:
                    summary["total_sincronizados"] += 1
                elif processed["resultado_verificacao"] == BlockVerificationItem.OUTCOME_REMOVED:
                    summary["total_ignorados"] += 1
                elif processed["resultado_verificacao"] == BlockVerificationItem.OUTCOME_ERROR:
                    summary["total_erros"] += 1

            run.finished_at = timezone.now()
            run.total_inicial_bloqueio = summary["total_inicial_bloqueio"]
            run.total_inicial_desbloqueio = summary["total_inicial_desbloqueio"]
            run.total_final_bloqueio = summary["total_final_bloqueio"]
            run.total_final_desbloqueio = summary["total_final_desbloqueio"]
            run.total_sincronizados = summary["total_sincronizados"]
            run.total_ignorados = summary["total_ignorados"]
            run.total_erros = summary["total_erros"]
            run.summary_message = self._build_verification_summary_message(summary)
            run.save(
                update_fields=[
                    "finished_at",
                    "total_inicial_bloqueio",
                    "total_inicial_desbloqueio",
                    "total_final_bloqueio",
                    "total_final_desbloqueio",
                    "total_sincronizados",
                    "total_ignorados",
                    "total_erros",
                    "summary_message",
                ]
            )
            summary["summary_message"] = run.summary_message
            if notify:
                self._notify_operational_check_status(summary)
            return summary
        except Exception as exc:
            run.status = BlockVerificationRun.STATUS_ERROR
            run.finished_at = timezone.now()
            run.summary_message = str(exc)
            run.save(update_fields=["status", "finished_at", "summary_message"])
            error_summary = dict(summary)
            error_summary["summary_message"] = str(exc)
            error_summary["status"] = "error"
            if notify:
                self._notify_operational_check_status(error_summary)
            raise

    def processar_bloqueios(self, result: BlockServiceResult, *, dry_run: bool = False) -> BlockServiceResult:
        ferias_list = []
        seen_collaborators: set[int] = set()
        for ferias in self.repository.buscar_para_bloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            ferias_list.append(ferias)
            
        if ferias_list:
            self._processar_bloqueios_em_lote(ferias_list, result=result, dry_run=dry_run)
        return result

    def processar_desbloqueios(self, result: BlockServiceResult, *, dry_run: bool = False) -> BlockServiceResult:
        ferias_list = []
        seen_collaborators: set[int] = set()
        for ferias in self.repository.buscar_para_desbloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            ferias_list.append(ferias)
            
        if ferias_list:
            self._processar_desbloqueios_em_lote(ferias_list, result=result, dry_run=dry_run)
        return result

    def processar_usuario_bloqueio(self, ferias, *, dry_run: bool = False) -> dict:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        sync_outcome = self._sincronizar_status_local_se_divergente(
            collaborator=collaborator,
            acao="BLOQUEIO",
            status_local=ad_status_atual,
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            dry_run=dry_run,
        )
        if sync_outcome:
            return sync_outcome

        if not self.repository.pode_bloquear(collaborator.id):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="BLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=ad_status_atual or "IGNORADO",
                vpn_status="IGNORADO",
                resultado="IGNORADO",
                mensagem="Bloqueio ignorado: status atual não exige bloqueio.",
            )
            return {"resultado": "IGNORADO"}

        if self.repository.ja_processado_hoje(collaborator.id, "BLOQUEIO"):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="BLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status="IGNORADO",
                vpn_status="IGNORADO",
                resultado="IGNORADO",
                mensagem="Bloqueio já executado com sucesso hoje.",
            )
            return {"resultado": "IGNORADO"}

        if dry_run:
            preflight = self._consultar_estado_ad(collaborator.login_ad or "")
            decisao = self._decidir_execucao_preflight(preflight, acao="BLOQUEIO")
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=preflight.get("usuario_ad") or (collaborator.login_ad or ""),
                email=collaborator.email or "",
                acao="BLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=preflight.get("ad_status") or ad_status_atual or "SIMULADO",
                vpn_status=preflight.get("vpn_status") or "SIMULADO",
                resultado="IGNORADO",
                mensagem=f"Simulacao: {decisao['mensagem']}",
            )
            return {"resultado": "IGNORADO"}

        preflight_outcome = self._executar_preflight_ou_ignorar(
            collaborator=collaborator,
            acao="BLOQUEIO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
        )
        if preflight_outcome:
            return preflight_outcome

        ad_result = bloquear_usuario_ad(collaborator.login_ad or "")
        ad_status = ad_result.get("ad_status", "ERRO")
        vpn_status = ad_result.get("vpn_status", "NP")
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"

        if resultado == "SUCESSO":
            self.repository.atualizar_status_block(
                colaborador_id=collaborator.id,
                ad_status=ad_status,
                vpn_status=vpn_status,
            )

        self.repository.salvar_resultado_execucao(
            colaborador_id=collaborator.id,
            usuario_ad=ad_result.get("usuario_ad") or (collaborator.login_ad or ""),
            email=collaborator.email or "",
            acao="BLOQUEIO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return {"resultado": resultado}

    def processar_usuario_desbloqueio(self, ferias, *, dry_run: bool = False) -> dict:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        sync_outcome = self._sincronizar_status_local_se_divergente(
            collaborator=collaborator,
            acao="DESBLOQUEIO",
            status_local=ad_status_atual,
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            dry_run=dry_run,
        )
        if sync_outcome:
            return sync_outcome

        if not self.repository.pode_desbloquear(collaborator.id):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="DESBLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=ad_status_atual or "IGNORADO",
                vpn_status="IGNORADO",
                resultado="IGNORADO",
                mensagem="Desbloqueio ignorado: status atual não exige desbloqueio.",
            )
            return {"resultado": "IGNORADO"}

        if self.repository.ja_processado_hoje(collaborator.id, "DESBLOQUEIO"):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="DESBLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status="IGNORADO",
                vpn_status="NP",
                resultado="IGNORADO",
                mensagem="Desbloqueio já executado com sucesso hoje.",
            )
            return {"resultado": "IGNORADO"}

        if dry_run:
            preflight = self._consultar_estado_ad(collaborator.login_ad or "")
            decisao = self._decidir_execucao_preflight(preflight, acao="DESBLOQUEIO")
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=preflight.get("usuario_ad") or (collaborator.login_ad or ""),
                email=collaborator.email or "",
                acao="DESBLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=preflight.get("ad_status") or ad_status_atual or "SIMULADO",
                vpn_status=preflight.get("vpn_status") or "SIMULADO",
                resultado="IGNORADO",
                mensagem=f"Simulacao: {decisao['mensagem']}",
            )
            return {"resultado": "IGNORADO"}

        preflight_outcome = self._executar_preflight_ou_ignorar(
            collaborator=collaborator,
            acao="DESBLOQUEIO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
        )
        if preflight_outcome:
            return preflight_outcome

        ad_result = desbloquear_usuario_ad(collaborator.login_ad or "")
        ad_status = ad_result.get("ad_status", "ERRO")
        vpn_status = ad_result.get("vpn_status", "NP")
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"

        if resultado == "SUCESSO":
            self.repository.atualizar_status_block(
                colaborador_id=collaborator.id,
                ad_status=ad_status,
                vpn_status=vpn_status,
            )

        self.repository.salvar_resultado_execucao(
            colaborador_id=collaborator.id,
            usuario_ad=ad_result.get("usuario_ad") or (collaborator.login_ad or ""),
            email=collaborator.email or "",
            acao="DESBLOQUEIO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return {"resultado": resultado}

    def testar_bloqueio(self) -> dict:
        usuario_teste = self.repository.obter_usuario_teste_block()
        if not usuario_teste:
            raise ValueError("Nenhum usuário de teste configurado no admin.")

        preflight_result = self._executar_preflight_teste_ou_ignorar(
            usuario_ad=usuario_teste,
            acao="BLOQUEIO",
            acao_historico="BLOQUEIO_TESTE",
        )
        if preflight_result:
            return preflight_result

        ad_result = bloquear_usuario_ad(usuario_teste)
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"
        self.repository.salvar_resultado_execucao(
            colaborador_id=0,
            usuario_ad=ad_result.get("usuario_ad") or usuario_teste,
            email="",
            acao="BLOQUEIO_TESTE",
            data_saida=None,
            data_retorno=None,
            ad_status=ad_result.get("ad_status", "ERRO"),
            vpn_status=ad_result.get("vpn_status", "NP"),
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return ad_result

    def testar_desbloqueio(self) -> dict:
        usuario_teste = self.repository.obter_usuario_teste_block()
        if not usuario_teste:
            raise ValueError("Nenhum usuário de teste configurado no admin.")

        preflight_result = self._executar_preflight_teste_ou_ignorar(
            usuario_ad=usuario_teste,
            acao="DESBLOQUEIO",
            acao_historico="DESBLOQUEIO_TESTE",
        )
        if preflight_result:
            return preflight_result

        ad_result = desbloquear_usuario_ad(usuario_teste)
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"
        self.repository.salvar_resultado_execucao(
            colaborador_id=0,
            usuario_ad=ad_result.get("usuario_ad") or usuario_teste,
            email="",
            acao="DESBLOQUEIO_TESTE",
            data_saida=None,
            data_retorno=None,
            ad_status=ad_result.get("ad_status", "ERRO"),
            vpn_status=ad_result.get("vpn_status", "NP"),
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return ad_result

    # INTERNAL HELPERS

    def _processar_fila_verificacao_operacional(
        self,
        verification_run: BlockVerificationRun,
        *,
        result: BlockServiceResult,
        dry_run: bool,
    ) -> BlockServiceResult:
        ferias_bloqueio = [
            self._ferias_from_verification_item(item)
            for item in verification_run.items.filter(acao_final="BLOQUEAR").order_by("colaborador_nome", "usuario_ad")
        ]
        if ferias_bloqueio:
            self._processar_bloqueios_em_lote(ferias_bloqueio, result=result, dry_run=dry_run)

        ferias_desbloqueio = [
            self._ferias_from_verification_item(item)
            for item in verification_run.items.filter(acao_final="DESBLOQUEAR").order_by("colaborador_nome", "usuario_ad")
        ]
        if ferias_desbloqueio:
            self._processar_desbloqueios_em_lote(ferias_desbloqueio, result=result, dry_run=dry_run)

        return result

    def _ferias_from_verification_item(self, item: BlockVerificationItem):
        collaborator = self.repository.obter_colaborador(item.colaborador_id)
        if collaborator is None:
            collaborator = SimpleNamespace(
                id=item.colaborador_id,
                nome=item.colaborador_nome,
                email=item.email,
                login_ad=item.usuario_ad,
            )
        return SimpleNamespace(
            colaborador=collaborator,
            colaborador_id=item.colaborador_id,
            data_saida=item.data_saida,
            data_retorno=item.data_retorno,
        )

    def _processar_bloqueios_em_lote(self, ferias_list: list, *, result: BlockServiceResult, dry_run: bool) -> None:
        candidatos_para_executar = self._preparar_candidatos_execucao(
            ferias_list,
            acao="BLOQUEIO",
            mensagem_ignorado="Bloqueio ignorado: AD e TOTVS ja estao coerentes com o estado esperado.",
            mensagem_simulacao="Simulacao: Execucao de bloqueio em lote para {sistemas}.",
            dry_run=dry_run,
            result=result,
        )
        if not candidatos_para_executar:
            return
        self._executar_lote_integrado(
            candidatos_para_executar,
            acao="BLOQUEIO",
            result=result,
        )
        return
        candidatos_para_executar = []
        for ferias in ferias_list:
            collaborator = ferias.colaborador
            if not self.repository.pode_bloquear(collaborator.id):
                self._registrar_ignorado(ferias, "Bloqueio ignorado: status atual não exige bloqueio.", acao="BLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="BLOQUEIO")
                continue
                
            if self.repository.ja_processado_hoje(collaborator.id, "BLOQUEIO"):
                self._registrar_ignorado(ferias, "Bloqueio já executado com sucesso hoje.", acao="BLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="BLOQUEIO")
                continue
                
            if dry_run:
                self._registrar_ignorado(ferias, "Simulacao: Execução de bloqueio em lote.", acao="BLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="BLOQUEIO")
                continue
                
            candidatos_para_executar.append(ferias)
            
        if not candidatos_para_executar:
            return
            
        usuarios_ad = [f.colaborador.login_ad for f in candidatos_para_executar if f.colaborador.login_ad]
        if not usuarios_ad:
            return
            
        resultados_ad = bloquear_usuarios_ad(usuarios_ad)
        resultados_lookup = {r.get("usuario_ad", "").strip().lower(): r for r in resultados_ad}
        
        for ferias in candidatos_para_executar:
            collaborator = ferias.colaborador
            ad_result = resultados_lookup.get((collaborator.login_ad or "").strip().lower(), {})
            if not ad_result:
                ad_result = self._error_consulta_operacional(collaborator.login_ad or "", "Não retornou no lote.")
                
            ad_status = ad_result.get("ad_status", "ERRO")
            vpn_status = ad_result.get("vpn_status", "NP")
            resultado_final = "SUCESSO" if ad_result.get("success") else "ERRO"
            
            if resultado_final == "SUCESSO":
                self.repository.atualizar_status_block(
                    colaborador_id=collaborator.id,
                    ad_status=ad_status,
                    vpn_status=vpn_status,
                )
                
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=ad_result.get("usuario_ad") or (collaborator.login_ad or ""),
                email=collaborator.email or "",
                acao="BLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=ad_status,
                vpn_status=vpn_status,
                resultado=resultado_final,
                mensagem=ad_result.get("message", ""),
            )
            self._acumular_resultado(result, {"resultado": resultado_final}, acao="BLOQUEIO")

    def _processar_desbloqueios_em_lote(self, ferias_list: list, *, result: BlockServiceResult, dry_run: bool) -> None:
        candidatos_para_executar = self._preparar_candidatos_execucao(
            ferias_list,
            acao="DESBLOQUEIO",
            mensagem_ignorado="Desbloqueio ignorado: AD e TOTVS ja estao coerentes com o estado esperado.",
            mensagem_simulacao="Simulacao: Execucao de desbloqueio em lote para {sistemas}.",
            dry_run=dry_run,
            result=result,
        )
        if not candidatos_para_executar:
            return
        self._executar_lote_integrado(
            candidatos_para_executar,
            acao="DESBLOQUEIO",
            result=result,
        )
        return
        candidatos_para_executar = []
        for ferias in ferias_list:
            collaborator = ferias.colaborador
            if not self.repository.pode_desbloquear(collaborator.id):
                self._registrar_ignorado(ferias, "Desbloqueio ignorado: status atual não exige desbloqueio.", acao="DESBLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="DESBLOQUEIO")
                continue
                
            if self.repository.ja_processado_hoje(collaborator.id, "DESBLOQUEIO"):
                self._registrar_ignorado(ferias, "Desbloqueio já executado com sucesso hoje.", acao="DESBLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="DESBLOQUEIO")
                continue
                
            if dry_run:
                self._registrar_ignorado(ferias, "Simulacao: Execução de desbloqueio em lote.", acao="DESBLOQUEIO")
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao="DESBLOQUEIO")
                continue
                
            candidatos_para_executar.append(ferias)
            
        if not candidatos_para_executar:
            return
            
        usuarios_ad = [f.colaborador.login_ad for f in candidatos_para_executar if f.colaborador.login_ad]
        if not usuarios_ad:
            return
            
        resultados_ad = desbloquear_usuarios_ad(usuarios_ad)
        resultados_lookup = {r.get("usuario_ad", "").strip().lower(): r for r in resultados_ad}
        
        for ferias in candidatos_para_executar:
            collaborator = ferias.colaborador
            ad_result = resultados_lookup.get((collaborator.login_ad or "").strip().lower(), {})
            if not ad_result:
                ad_result = self._error_consulta_operacional(collaborator.login_ad or "", "Não retornou no lote.")
                
            ad_status = ad_result.get("ad_status", "ERRO")
            vpn_status = ad_result.get("vpn_status", "NP")
            resultado_final = "SUCESSO" if ad_result.get("success") else "ERRO"
            
            if resultado_final == "SUCESSO":
                self.repository.atualizar_status_block(
                    colaborador_id=collaborator.id,
                    ad_status=ad_status,
                    vpn_status=vpn_status,
                )
                
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=ad_result.get("usuario_ad") or (collaborator.login_ad or ""),
                email=collaborator.email or "",
                acao="DESBLOQUEIO",
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=ad_status,
                vpn_status=vpn_status,
                resultado=resultado_final,
                mensagem=ad_result.get("message", ""),
            )
            self._acumular_resultado(result, {"resultado": resultado_final}, acao="DESBLOQUEIO")

    def _preparar_candidatos_execucao(
        self,
        ferias_list: list,
        *,
        acao: str,
        mensagem_ignorado: str,
        mensagem_simulacao: str,
        dry_run: bool,
        result: BlockServiceResult,
    ) -> list[dict]:
        candidatos_para_executar = []
        for ferias in ferias_list:
            collaborator = ferias.colaborador
            if acao == "BLOQUEIO":
                executar_ad = self.repository.pode_executar_bloqueio_ad(collaborator.id)
                executar_totvs = self.repository.pode_executar_bloqueio_totvs(collaborator.id)
            else:
                executar_ad = self.repository.pode_executar_desbloqueio_ad(collaborator.id)
                executar_totvs = self.repository.pode_executar_desbloqueio_totvs(collaborator.id)

            if not executar_ad and not executar_totvs:
                self._registrar_ignorado(ferias, mensagem_ignorado, acao=acao)
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao=acao)
                continue

            if self.repository.ja_processado_hoje(collaborator.id, acao):
                acao_legivel = "Bloqueio" if acao == "BLOQUEIO" else "Desbloqueio"
                self._registrar_ignorado(
                    ferias,
                    f"{acao_legivel} ja executado com sucesso hoje.",
                    acao=acao,
                )
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao=acao)
                continue

            if dry_run:
                sistemas = []
                if executar_ad:
                    sistemas.append("AD")
                if executar_totvs:
                    sistemas.append("TOTVS")
                self._registrar_ignorado(
                    ferias,
                    mensagem_simulacao.format(sistemas=", ".join(sistemas)),
                    acao=acao,
                )
                self._acumular_resultado(result, {"resultado": "IGNORADO"}, acao=acao)
                continue

            candidatos_para_executar.append(
                {
                    "ferias": ferias,
                    "executar_ad": executar_ad,
                    "executar_totvs": executar_totvs,
                }
            )
        return candidatos_para_executar

    def _executar_lote_integrado(
        self,
        candidatos_para_executar: list[dict],
        *,
        acao: str,
        result: BlockServiceResult,
    ) -> None:
        usuarios_ad = [
            item["ferias"].colaborador.login_ad
            for item in candidatos_para_executar
            if item["executar_ad"] and item["ferias"].colaborador.login_ad
        ]
        resultados_ad_lookup = {}
        if usuarios_ad:
            executor_ad = bloquear_usuarios_ad if acao == "BLOQUEIO" else desbloquear_usuarios_ad
            resultados_ad = executor_ad(usuarios_ad)
            resultados_ad_lookup = {r.get("usuario_ad", "").strip().lower(): r for r in resultados_ad}

        usuarios_totvs = [
            item["ferias"].colaborador.login_ad
            for item in candidatos_para_executar
            if item["executar_totvs"] and item["ferias"].colaborador.login_ad
        ]
        resultados_totvs_lookup = {}
        if usuarios_totvs:
            executor_totvs = (
                self.totvs_service.bloquear_usuarios_operacionais
                if acao == "BLOQUEIO"
                else self.totvs_service.desbloquear_usuarios_operacionais
            )
            resultados_totvs = executor_totvs(usuarios_totvs)
            resultados_totvs_lookup = {r.get("usuario_ad", "").strip().lower(): r for r in resultados_totvs}

        for item in candidatos_para_executar:
            ferias = item["ferias"]
            collaborator = ferias.colaborador
            usuario_ad = (collaborator.login_ad or "").strip()
            chave = usuario_ad.lower()

            ad_status_atual = self.repository.obter_status_ad(collaborator.id) or ""
            vpn_status_atual = self.repository.obter_status_vpn(collaborator.id) or ""
            totvs_status_atual = self.repository.obter_status_totvs(collaborator.id) or ""

            ad_result = None
            if item["executar_ad"]:
                ad_result = resultados_ad_lookup.get(chave)
                if not ad_result:
                    ad_result = self._error_consulta_operacional(
                        usuario_ad,
                        "Nao retornou no lote do AD.",
                    )

            totvs_result = None
            if item["executar_totvs"]:
                totvs_result = resultados_totvs_lookup.get(chave)
                if not totvs_result:
                    totvs_result = self._error_consulta_totvs(
                        usuario_ad,
                        "Nao retornou no lote controlado do TOTVS.",
                    )

            ad_success = ad_result is None or bool(ad_result.get("success"))
            totvs_success = totvs_result is None or bool(totvs_result.get("success"))
            ad_status_final = ad_result.get("ad_status", ad_status_atual) if ad_result is not None else ad_status_atual
            vpn_status_final = ad_result.get("vpn_status", vpn_status_atual) if ad_result is not None else vpn_status_atual
            totvs_status_final = (
                totvs_result.get("totvs_status", totvs_status_atual)
                if totvs_result is not None
                else totvs_status_atual
            )

            self.repository.atualizar_status_block(
                colaborador_id=collaborator.id,
                ad_status=ad_status_final if ad_success else ad_status_atual,
                vpn_status=vpn_status_final if ad_success else vpn_status_atual,
                totvs_status=totvs_status_final if totvs_success else totvs_status_atual,
            )

            mensagens = []
            if ad_result is not None:
                mensagens.append(f"AD: {ad_result.get('message', '')}".strip())
            if totvs_result is not None:
                mensagens.append(f"TOTVS: {totvs_result.get('message', '')}".strip())

            resultado_final = "SUCESSO" if ad_success and totvs_success else "ERRO"
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=usuario_ad,
                email=collaborator.email or "",
                acao=acao,
                data_saida=ferias.data_saida,
                data_retorno=ferias.data_retorno,
                ad_status=ad_status_final if ad_success else ad_status_atual,
                vpn_status=vpn_status_final if ad_success else vpn_status_atual,
                totvs_status=totvs_status_final if totvs_success else totvs_status_atual,
                resultado=resultado_final,
                mensagem=" | ".join([mensagem for mensagem in mensagens if mensagem]),
            )
            self._acumular_resultado(result, {"resultado": resultado_final}, acao=acao)

    def _registrar_ignorado(self, ferias, mensagem: str, *, acao: str) -> None:
        collaborator = ferias.colaborador
        self.repository.salvar_resultado_execucao(
            colaborador_id=collaborator.id,
            usuario_ad=collaborator.login_ad or "",
            email=collaborator.email or "",
            acao=acao,
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status=self.repository.obter_status_ad(collaborator.id) or "IGNORADO",
            vpn_status=self.repository.obter_status_vpn(collaborator.id) or "IGNORADO",
            totvs_status=self.repository.obter_status_totvs(collaborator.id) or "IGNORADO",
            resultado="IGNORADO",
            mensagem=mensagem,
        )

    def _consultar_estado_ad(self, usuario_ad: str) -> dict:
        if not usuario_ad.strip():
            return {
                "success": False,
                "usuario_ad": usuario_ad,
                "ad_status": "ERRO",
                "vpn_status": "NP",
                "message": "Usuario AD vazio.",
            }
        return consultar_usuario_ad(usuario_ad.strip())

    def _build_verification_candidates(self) -> list[dict]:
        preview = self.preview_service.previsualizar_verificacao_block()
        if not preview["rows"]:
            return []

        ferias_bloqueio = {
            ferias.colaborador_id: ferias
            for ferias in self.repository.buscar_para_bloqueio_hoje()
        }
        ferias_desbloqueio = {
            ferias.colaborador_id: ferias
            for ferias in self.repository.buscar_para_desbloqueio_hoje()
        }

        rows: list[dict] = []
        for row in preview["rows"]:
            colaborador = self.repository.obter_colaborador_por_login_ou_email(
                usuario_ad=row["usuario_ad"],
                email=row["email"],
            )
            if not colaborador:
                continue

            acao_prevista = row["acao_prevista"]
            if acao_prevista == "IGNORAR":
                acao_prevista = "BLOQUEAR" if row.get("acao_ordem") == 0 else "DESBLOQUEAR"

            if acao_prevista == "BLOQUEAR":
                ferias = ferias_bloqueio.get(colaborador.id)
                if ferias:
                    rows.append(self._build_verification_candidate(ferias, acao_inicial="BLOQUEAR"))
            elif acao_prevista == "DESBLOQUEAR":
                ferias = ferias_desbloqueio.get(colaborador.id)
                if ferias:
                    rows.append(self._build_verification_candidate(ferias, acao_inicial="DESBLOQUEAR"))
        return rows

    def _build_verification_candidate(self, ferias, *, acao_inicial: str) -> dict:
        collaborator = ferias.colaborador
        ad_status = self.repository.obter_status_ad(collaborator.id)
        vpn_status = self.repository.obter_status_vpn(collaborator.id)
        totvs_status = self.repository.obter_status_totvs(collaborator.id)
        motivo_inicial = self._motivo_inicial_verificacao(ferias, acao_inicial=acao_inicial)
        return {
            "colaborador_id": collaborator.id,
            "colaborador_nome": collaborator.nome,
            "usuario_ad": collaborator.login_ad or "",
            "email": collaborator.email or "",
            "data_saida": ferias.data_saida,
            "data_retorno": ferias.data_retorno,
            "acao_inicial": acao_inicial,
            "ad_status_banco_antes": ad_status,
            "vpn_status_banco_antes": vpn_status,
            "totvs_status_banco_antes": totvs_status,
            "motivo_inicial": motivo_inicial,
            "force_operational_check": self._should_force_operational_check(ad_status, vpn_status),
            "force_totvs_operational_check": self._should_force_totvs_operational_check(totvs_status),
        }

    def _process_verification_candidate(
        self,
        item: dict,
        *,
        ad_lookup: dict[str, dict],
        totvs_lookup: dict[str, dict],
    ) -> dict:
        candidate = dict(item)
        acao_inicial = candidate["acao_inicial"]
        colaborador_id = candidate["colaborador_id"]
        ad_status_banco = candidate["ad_status_banco_antes"]
        vpn_status_banco = candidate["vpn_status_banco_antes"]
        totvs_status_banco = candidate["totvs_status_banco_antes"]

        if self.repository.ja_processado_hoje(colaborador_id, "BLOQUEIO" if acao_inicial == "BLOQUEAR" else "DESBLOQUEIO"):
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_REMOVED,
                ad_status_real=ad_status_banco,
                vpn_status_real=vpn_status_banco,
                totvs_status_real=totvs_status_banco,
                ad_status_banco_depois=ad_status_banco,
                vpn_status_banco_depois=vpn_status_banco,
                totvs_status_banco_depois=totvs_status_banco,
                motivo="Ja processado hoje com sucesso.",
            )
            return candidate

        ad_real = ad_lookup.get(candidate["usuario_ad"].strip().lower()) or self._error_consulta_operacional(
            candidate["usuario_ad"],
            "Usuario nao retornado pela consulta em lote.",
        )
        vpn_status_real = self._vpn_status_from_group_membership(ad_real) if ad_real.get("success") else "NP"
        candidate["ad_status_real"] = ad_real.get("ad_status", "ERRO")
        candidate["vpn_status_real"] = vpn_status_real

        if not ad_real.get("success"):
            if (
                self._is_missing_ad_user_result(ad_real)
                and self._normalizar_status_ad(ad_status_banco) == "NP"
                and self._normalizar_status_vpn(vpn_status_banco) == "NP"
            ):
                candidate.update(
                    acao_final="IGNORAR",
                    resultado_verificacao=BlockVerificationItem.OUTCOME_REMOVED,
                    totvs_status_real=totvs_status_banco,
                    ad_status_banco_depois=ad_status_banco,
                    vpn_status_banco_depois=vpn_status_banco,
                    totvs_status_banco_depois=totvs_status_banco,
                    motivo="Usuario nao encontrado no AD; status NP mantido no banco sem acao final.",
                )
                return candidate
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_ERROR,
                totvs_status_real=totvs_status_banco,
                ad_status_banco_depois=ad_status_banco,
                vpn_status_banco_depois=vpn_status_banco,
                totvs_status_banco_depois=totvs_status_banco,
                motivo=self._build_operational_lookup_failure_message(
                    usuario_ad=candidate["usuario_ad"],
                    ad_result=ad_real,
                ),
            )
            return candidate

        ad_real_normalizado = self._normalizar_status_ad(ad_real.get("ad_status") or "")
        vpn_real_normalizado = self._normalizar_status_vpn(vpn_status_real)
        ad_status_banco_depois = ad_real.get("ad_status", ad_status_banco)
        vpn_status_banco_depois = vpn_status_real
        sync_messages: list[str] = []
        ad_changed = self._normalizar_status_ad(ad_status_banco) != ad_real_normalizado
        vpn_changed = self._normalizar_status_vpn(vpn_status_banco) != vpn_real_normalizado

        if ad_changed or vpn_changed:
            self.repository.atualizar_status_block(
                colaborador_id=colaborador_id,
                ad_status=ad_status_banco_depois,
                vpn_status=vpn_status_banco_depois,
            )
            sync_messages.append(
                f"AD/VPN sincronizados para {ad_status_banco_depois}/{vpn_status_banco_depois}."
            )
            self._notificar_divergencia_operacional_sync(
                candidate=candidate,
                ad_real=ad_real,
                status_banco_antes=ad_status_banco,
                vpn_status_banco_antes=vpn_status_banco,
                vpn_status_real=vpn_status_real,
                vpn_changed=vpn_changed,
            )

        desired_ad = "BLOQUEADO" if acao_inicial == "BLOQUEAR" else "LIBERADO"
        ad_needs_action = ad_real_normalizado != desired_ad

        totvs_real = totvs_lookup.get(candidate["usuario_ad"].strip().lower()) or self._error_consulta_totvs(
            candidate["usuario_ad"],
            "Usuario nao retornado pela consulta controlada do TOTVS.",
        )
        candidate["totvs_status_real"] = totvs_real.get("totvs_status", "ERRO")
        if not totvs_real.get("success"):
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_ERROR,
                ad_status_banco_depois=ad_status_banco_depois,
                vpn_status_banco_depois=vpn_status_banco_depois,
                totvs_status_banco_depois=totvs_status_banco,
                motivo=totvs_real.get("message", "Falha ao consultar TOTVS."),
            )
            return candidate

        totvs_found = bool(totvs_real.get("user_found"))
        totvs_real_normalizado = self._normalizar_status_totvs(totvs_real.get("totvs_status") or "")
        totvs_status_banco_depois = totvs_status_banco
        totvs_status_banco_normalizado = self._normalizar_status_totvs(totvs_status_banco)
        if not totvs_found:
            totvs_real_normalizado = "NP"
            candidate["totvs_status_real"] = "NP"
            if totvs_status_banco_normalizado and totvs_status_banco_normalizado != "NP":
                totvs_status_banco_depois = "NP"
                self.repository.atualizar_status_block(
                    colaborador_id=colaborador_id,
                    ad_status=ad_status_banco_depois,
                    vpn_status=vpn_status_banco_depois,
                    totvs_status="NP",
                )
                sync_messages.append("TOTVS nao encontrado e status local ajustado para NP.")
        else:
            totvs_status_banco_depois = totvs_real.get("totvs_status", totvs_status_banco)
            if totvs_status_banco_normalizado and totvs_status_banco_normalizado != totvs_real_normalizado:
                self.repository.atualizar_status_block(
                    colaborador_id=colaborador_id,
                    ad_status=ad_status_banco_depois,
                    vpn_status=vpn_status_banco_depois,
                    totvs_status=totvs_status_banco_depois,
                )
                sync_messages.append(f"TOTVS sincronizado para {totvs_status_banco_depois}.")
            elif not totvs_status_banco_normalizado:
                totvs_status_banco_depois = totvs_status_banco

        desired_totvs = "BLOQUEADO" if acao_inicial == "BLOQUEAR" else "LIBERADO"
        totvs_needs_action = totvs_found and totvs_real_normalizado != desired_totvs

        candidate["ad_status_banco_depois"] = ad_status_banco_depois
        candidate["vpn_status_banco_depois"] = vpn_status_banco_depois
        candidate["totvs_status_banco_depois"] = totvs_status_banco_depois

        pending_systems = []
        if ad_needs_action:
            pending_systems.append("AD")
        if totvs_needs_action:
            pending_systems.append("TOTVS")

        if pending_systems:
            candidate.update(
                acao_final=acao_inicial,
                resultado_verificacao=BlockVerificationItem.OUTCOME_KEPT,
                motivo=(
                    f"Mantido na fila final. {candidate['motivo_inicial']} "
                    f"Sistemas pendentes: {', '.join(pending_systems)}."
                ),
            )
            return candidate

        if sync_messages:
            friendly_sync_message = " ".join(sync_messages)
            if ad_changed and not pending_systems and ad_real_normalizado == desired_ad:
                if desired_ad == "LIBERADO":
                    friendly_sync_message = "Usuario ja estava liberado no AD; banco sincronizado antes da fila final."
                else:
                    friendly_sync_message = "Usuario ja estava bloqueado no AD; banco sincronizado antes da fila final."
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_SYNCED,
                motivo=friendly_sync_message,
            )
            return candidate

        candidate.update(
            acao_final="IGNORAR",
            resultado_verificacao=BlockVerificationItem.OUTCOME_REMOVED,
            motivo="Sem acao necessaria apos validacao operacional.",
        )
        return candidate

    def _notificar_divergencia_operacional_sync(
        self,
        *,
        candidate: dict,
        ad_real: dict,
        status_banco_antes: str,
        vpn_status_banco_antes: str,
        vpn_status_real: str,
        vpn_changed: bool,
    ) -> None:
        try:
            self.notification_service.notify_operational_divergence(
                collaborator_id=candidate["colaborador_id"],
                collaborator_name=candidate["colaborador_nome"],
                usuario_ad=candidate.get("usuario_ad") or "",
                email=candidate.get("email") or "",
                system_name="AD PRIN",
                initial_action=candidate["acao_inicial"],
                sheet_status=status_banco_antes or "",
                real_status=ad_real.get("ad_status", ""),
                internal_status_after_sync=ad_real.get("ad_status", ""),
                vpn_sheet_status=vpn_status_banco_antes or "",
                vpn_real_status=vpn_status_real or "",
                vpn_internal_status_after_sync=vpn_status_real or "",
                vpn_changed=vpn_changed,
                data_saida=candidate.get("data_saida"),
                data_retorno=candidate.get("data_retorno"),
                details={
                    "motivo_inicial": candidate.get("motivo_inicial") or "",
                    "vpn_status_real": vpn_status_real or "",
                    "vpn_status_banco_antes": vpn_status_banco_antes or "",
                    "is_in_printi_acesso": bool(ad_real.get("is_in_printi_acesso", False)),
                    "status_banco_antes": status_banco_antes or "",
                },
            )
        except Exception:
            logger.exception(
                "Falha ao enviar notificacao de divergencia operacional para colaborador_id=%s usuario_ad=%s",
                candidate.get("colaborador_id"),
                candidate.get("usuario_ad"),
            )

    def _consultar_estados_ad_operacionais(self, items: list[dict]) -> dict[str, dict]:
        usuarios = []
        for item in items:
            colaborador_id = item["colaborador_id"]
            acao = "BLOQUEIO" if item["acao_inicial"] == "BLOQUEAR" else "DESBLOQUEIO"
            usuario_ad = (item.get("usuario_ad") or "").strip()
            if not usuario_ad:
                continue
            if self.repository.ja_processado_hoje(colaborador_id, acao):
                continue
            usuarios.append(usuario_ad)

        if not usuarios:
            return {}

        resultados = consultar_usuarios_ad(usuarios)
        lookup = {}
        for resultado in resultados:
            chave = (resultado.get("usuario_ad") or "").strip().lower()
            if chave:
                lookup[chave] = resultado
        return lookup

    def _consultar_estados_totvs_operacionais(self, items: list[dict]) -> dict[str, dict]:
        usuarios = []
        for item in items:
            usuario_ad = (item.get("usuario_ad") or "").strip()
            if usuario_ad:
                usuarios.append(usuario_ad)

        if not usuarios:
            return {}

        resultados = self.totvs_service.consultar_usuarios_operacionais(usuarios)
        lookup = {}
        for resultado in resultados:
            chave = (resultado.get("usuario_ad") or "").strip().lower()
            if chave:
                lookup[chave] = resultado
        return lookup

    def _error_consulta_operacional(self, usuario_ad: str, message: str) -> dict:
        return {
            "success": False,
            "usuario_ad": usuario_ad,
            "ad_status": "ERRO",
            "vpn_status": "NP",
            "message": message,
            "user_found": False,
            "is_enabled": False,
            "is_in_printi_acesso": False,
            "already_in_desired_state": False,
        }

    def _error_consulta_totvs(self, usuario_ad: str, message: str) -> dict:
        return {
            "success": False,
            "usuario_ad": usuario_ad,
            "totvs_status": "ERRO",
            "message": message,
            "user_found": False,
            "active": False,
        }

    def _motivo_inicial_verificacao(self, ferias, *, acao_inicial: str) -> str:
        today = timezone.localdate()
        if acao_inicial == "BLOQUEAR":
            return "Saindo de férias hoje." if ferias.data_saida == today else "Em férias e ainda não bloqueado."
        return "Retornando de férias hoje." if ferias.data_retorno == today else "Já retornou e ainda está bloqueado."

    def _vpn_status_from_group_membership(self, ad_result: dict) -> str:
        return "LIBERADA" if ad_result.get("is_in_printi_acesso", False) else "NP"

    def _normalizar_status_vpn(self, vpn_status: str) -> str:
        value = (vpn_status or "").strip().upper()
        if value in {"LIBERADA", "LIBERADO"}:
            return "LIBERADA"
        if value in {"NP", "NB", "", "-"}:
            return "NP"
        return value

    def _normalizar_status_totvs(self, status: str) -> str:
        value = (status or "").strip().upper()
        if value in {"BLOQUEADO", "BLOQUEADA"}:
            return "BLOQUEADO"
        if value in {"LIBERADO", "LIBERADA"}:
            return "LIBERADO"
        if value in {"NP", "", "-"}:
            return "NP"
        if value == "NB":
            return "NB"
        return value

    def _should_force_totvs_operational_check(self, status: str) -> bool:
        return self._normalizar_status_totvs(status) in {"NB", "NP"}

    def _should_force_operational_check(self, ad_status: str, vpn_status: str) -> bool:
        return self._normalizar_status_ad(ad_status) == "NP" and self._normalizar_status_vpn(vpn_status) == "NP"

    def _is_missing_ad_user_result(self, ad_result: dict) -> bool:
        if ad_result.get("user_found"):
            return False
        message = (ad_result.get("message") or "").strip().lower()
        return "nao encontrado" in message or "não encontrado" in message

    def _is_user_not_found_lookup_error(self, ad_result: dict) -> bool:
        if ad_result.get("user_found"):
            return False
        message = (ad_result.get("message") or "").strip().lower()
        markers = (
            "nao encontrado",
            "nÃ£o encontrado",
            "localizar um objeto",
            "nao e possivel localizar um objeto",
            "nao Ã© possivel localizar um objeto",
            "nÃ£o Ã© possÃ­vel localizar um objeto",
            "cannot find an object with identity",
        )
        return any(marker in message for marker in markers)

    def _build_operational_lookup_failure_message(self, *, usuario_ad: str, ad_result: dict) -> str:
        original_message = ad_result.get("message", "Sem detalhe")
        if self._is_user_not_found_lookup_error(ad_result):
            return (
                f"Usuario nao encontrado no AD para o login '{usuario_ad}'. "
                f"Verifique se o login_ad esta correto ou se a conta ainda existe no dominio. "
                f"Detalhe tecnico: {original_message}"
            )
        return f"Falha ao validar no AD: {original_message}"

    def _build_verification_summary_message(self, summary: dict) -> str:
        return (
            f"Lista inicial: bloquear={summary['total_inicial_bloqueio']}, "
            f"desbloquear={summary['total_inicial_desbloqueio']}. "
            f"Lista final: bloquear={summary['total_final_bloqueio']}, "
            f"desbloquear={summary['total_final_desbloqueio']}. "
            f"Sincronizados={summary['total_sincronizados']} | "
            f"Ignorados={summary['total_ignorados']} | "
            f"Erros={summary['total_erros']}."
        )

    def _build_block_execution_summary_message(self, payload: dict) -> str:
        return (
            f"Bloqueios={payload.get('bloqueios_feitos', 0)} | "
            f"Desbloqueios={payload.get('desbloqueios_feitos', 0)} | "
            f"Sincronizados={payload.get('sincronizados', 0)} | "
            f"Ignorados={payload.get('ignorados', 0)} | "
            f"Erros={payload.get('erros', 0)}."
        )

    def _notify_operational_check_status(self, summary: dict) -> None:
        self.notification_service.notify_task_status(
            task_key="block_operational_check",
            task_label="Check operacional do block",
            status=summary.get("status", "success"),
            summary=summary.get("summary_message", "Check operacional finalizado."),
            details=[
                f"Run ID: {summary.get('run_id', '-')}",
                f"Fila inicial bloquear: {summary.get('total_inicial_bloqueio', 0)}",
                f"Fila inicial desbloquear: {summary.get('total_inicial_desbloqueio', 0)}",
                f"Fila final bloquear: {summary.get('total_final_bloqueio', 0)}",
                f"Fila final desbloquear: {summary.get('total_final_desbloqueio', 0)}",
                f"Sincronizados: {summary.get('total_sincronizados', 0)}",
                f"Ignorados: {summary.get('total_ignorados', 0)}",
                f"Erros: {summary.get('total_erros', 0)}",
            ],
        )

    def _notify_block_execution_status(self, payload: dict) -> None:
        self.notification_service.notify_task_status(
            task_key="block_execution",
            task_label="Execucao final de block/desblock",
            status=payload.get("status", "success" if not payload.get("skipped") else "skipped"),
            summary=payload.get("message", self._build_block_execution_summary_message(payload)),
            details=[
                f"Dry run: {'sim' if payload.get('dry_run') else 'nao'}",
                f"Usou fila operacional: {'sim' if payload.get('used_operational_queue') else 'nao'}",
                f"Verification run: {payload.get('verification_run_id', '-')}",
                f"Bloqueios: {payload.get('bloqueios_feitos', 0)}",
                f"Desbloqueios: {payload.get('desbloqueios_feitos', 0)}",
                f"Sincronizados: {payload.get('sincronizados', 0)}",
                f"Ignorados: {payload.get('ignorados', 0)}",
                f"Erros: {payload.get('erros', 0)}",
            ],
        )

    def _decidir_execucao_preflight(self, preflight: dict, *, acao: str) -> dict:
        if not preflight.get("success"):
            return {
                "executar": False,
                "resultado": "ERRO",
                "label": "Erro na consulta",
                "mensagem": f"Consulta AD falhou; nenhuma alteração será executada. {preflight.get('message', '')}",
            }

        ad_status = (preflight.get("ad_status") or "").strip().upper()
        if acao == "BLOQUEIO":
            if ad_status in {"BLOQUEADO", "BLOQUEADA"}:
                return {
                    "executar": False,
                    "resultado": "SINCRONIZADO",
                    "label": "Sincronizar",
                    "mensagem": "AD real já está bloqueado; status local será atualizado sem executar bloqueio.",
                }
            if ad_status == "LIBERADO":
                return {
                    "executar": True,
                    "resultado": "PENDENTE",
                    "label": "Executar",
                    "mensagem": "AD real está liberado; bloqueio será executado.",
                }

        if acao == "DESBLOQUEIO":
            if ad_status == "LIBERADO":
                return {
                    "executar": False,
                    "resultado": "SINCRONIZADO",
                    "label": "Sincronizar",
                    "mensagem": "AD real já está liberado; status local será atualizado sem executar desbloqueio.",
                }
            if ad_status in {"BLOQUEADO", "BLOQUEADA"}:
                return {
                    "executar": True,
                    "resultado": "PENDENTE",
                    "label": "Executar",
                    "mensagem": "AD real está bloqueado; desbloqueio será executado.",
                }

        return {
            "executar": False,
            "resultado": "ERRO",
            "label": "Revisar",
            "mensagem": f"Status real do AD inesperado ({ad_status or 'vazio'}); nenhuma alteração será executada.",
        }

    def _decidir_sincronizacao_status_local(self, status_local: str, preflight: dict) -> dict | None:
        if not preflight.get("success"):
            return None

        local = self._normalizar_status_ad(status_local)
        real = self._normalizar_status_ad(preflight.get("ad_status") or "")
        if not real or local == real:
            return None

        return {
            "executar": False,
            "resultado": "SINCRONIZADO",
            "label": "Sincronizar",
            "mensagem": (
                f"Status local estava {local or 'VAZIO'}, mas o AD real está {real}; "
                "status local será atualizado sem executar alteração no AD."
            ),
        }

    def _normalizar_status_ad(self, status: str) -> str:
        status = (status or "").strip().upper()
        if status in {"BLOQUEADO", "BLOQUEADA"}:
            return "BLOQUEADO"
        if status in {"LIBERADO", "LIBERADA"}:
            return "LIBERADO"
        return status

    def _sincronizar_status_local_se_divergente(
        self,
        *,
        collaborator,
        acao: str,
        status_local: str,
        data_saida,
        data_retorno,
        dry_run: bool,
    ) -> dict | None:
        preflight = self._consultar_estado_ad(collaborator.login_ad or "")
        decisao = self._decidir_sincronizacao_status_local(status_local, preflight)
        if not decisao:
            return None

        ad_status = preflight.get("ad_status") or "ERRO"
        vpn_status = preflight.get("vpn_status") or "NP"
        if not dry_run:
            self.repository.atualizar_status_block(
                colaborador_id=collaborator.id,
                ad_status=ad_status,
                vpn_status=vpn_status,
            )

        self.repository.salvar_resultado_execucao(
            colaborador_id=collaborator.id,
            usuario_ad=preflight.get("usuario_ad") or (collaborator.login_ad or ""),
            email=collaborator.email or "",
            acao=acao,
            data_saida=data_saida,
            data_retorno=data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado="SINCRONIZADO",
            mensagem=(
                f"Simulacao: {decisao['mensagem']}"
                if dry_run
                else decisao["mensagem"]
            ),
        )
        return {"resultado": "SINCRONIZADO"}

    def _executar_preflight_ou_ignorar(
        self,
        *,
        collaborator,
        acao: str,
        data_saida,
        data_retorno,
    ) -> dict | None:
        preflight = self._consultar_estado_ad(collaborator.login_ad or "")
        decisao = self._decidir_execucao_preflight(preflight, acao=acao)
        if decisao["executar"]:
            return None

        resultado = decisao["resultado"]
        ad_status = preflight.get("ad_status") or "ERRO"
        vpn_status = preflight.get("vpn_status") or "NP"
        if resultado == "SINCRONIZADO":
            self.repository.atualizar_status_block(
                colaborador_id=collaborator.id,
                ad_status=ad_status,
                vpn_status=vpn_status,
            )

        self.repository.salvar_resultado_execucao(
            colaborador_id=collaborator.id,
            usuario_ad=preflight.get("usuario_ad") or (collaborator.login_ad or ""),
            email=collaborator.email or "",
            acao=acao,
            data_saida=data_saida,
            data_retorno=data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=decisao["mensagem"],
        )
        return {"resultado": resultado}

    def _executar_preflight_teste_ou_ignorar(
        self,
        *,
        usuario_ad: str,
        acao: str,
        acao_historico: str,
    ) -> dict | None:
        preflight = self._consultar_estado_ad(usuario_ad)
        decisao = self._decidir_execucao_preflight(preflight, acao=acao)
        if decisao["executar"]:
            return None

        resultado = decisao["resultado"]
        self.repository.salvar_resultado_execucao(
            colaborador_id=0,
            usuario_ad=preflight.get("usuario_ad") or usuario_ad,
            email="",
            acao=acao_historico,
            data_saida=None,
            data_retorno=None,
            ad_status=preflight.get("ad_status", "ERRO"),
            vpn_status=preflight.get("vpn_status", "NP"),
            resultado=resultado,
            mensagem=decisao["mensagem"],
        )
        return {
            "success": resultado != "ERRO",
            "usuario_ad": preflight.get("usuario_ad") or usuario_ad,
            "ad_status": preflight.get("ad_status", "ERRO"),
            "vpn_status": preflight.get("vpn_status", "NP"),
            "message": decisao["mensagem"],
            "user_found": preflight.get("user_found", False),
            "is_in_printi_acesso": preflight.get("is_in_printi_acesso", False),
            "already_in_desired_state": resultado == "SINCRONIZADO",
        }

    def _acumular_resultado(self, result: BlockServiceResult, outcome: dict, *, acao: str) -> None:
        resultado = outcome.get("resultado")
        if resultado == "SUCESSO" and acao == "BLOQUEIO":
            result.bloqueios_feitos += 1
        elif resultado == "SUCESSO" and acao == "DESBLOQUEIO":
            result.desbloqueios_feitos += 1
        elif resultado == "SINCRONIZADO":
            result.sincronizados += 1
        elif resultado == "IGNORADO":
            result.ignorados += 1
        else:
            result.erros += 1
