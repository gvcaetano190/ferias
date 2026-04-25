from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from django.utils import timezone

from apps.block.models import BlockVerificationItem, BlockVerificationRun
from apps.block.repositories import BlockRepository
from integrations.ad.executor import bloquear_usuario_ad, consultar_usuario_ad, consultar_usuarios_ad, desbloquear_usuario_ad


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


class BlockService:
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

    def processar_verificacao_block(self, *, require_operational_queue: bool = False) -> dict:
        config = self.repository.obter_configuracao_ativa_block()
        dry_run = bool(config and config.dry_run)
        result = BlockServiceResult()
        verification_run = self._obter_verificacao_operacional_pronta()
        if require_operational_queue and not verification_run:
            payload = result.as_dict()
            payload["dry_run"] = dry_run
            payload["verification_run_id"] = None
            payload["used_operational_queue"] = False
            payload["skipped"] = True
            payload["message"] = (
                "Verificacao block aguardando uma verificacao operacional concluida hoje para usar a fila final."
            )
            return payload
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
        return payload

    def processar_verificacao_operacional_block(self) -> dict:
        run = BlockVerificationRun.objects.create(status=BlockVerificationRun.STATUS_SUCCESS)
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
            summary["total_inicial_bloqueio"] = sum(1 for item in items if item["acao_inicial"] == "BLOQUEAR")
            summary["total_inicial_desbloqueio"] = sum(1 for item in items if item["acao_inicial"] == "DESBLOQUEAR")

            for item in items:
                processed = self._process_verification_candidate(item, ad_lookup=ad_lookup)
                self._create_verification_item(run, processed)
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
            return summary
        except Exception as exc:
            run.status = BlockVerificationRun.STATUS_ERROR
            run.finished_at = timezone.now()
            run.summary_message = str(exc)
            run.save(update_fields=["status", "finished_at", "summary_message"])
            raise

    def ver_detalhes_verificacao_operacional(self, *, run_id: int | None = None) -> dict:
        if run_id:
            run = BlockVerificationRun.objects.prefetch_related("items").filter(pk=run_id).first()
        else:
            run = BlockVerificationRun.objects.prefetch_related("items").first()

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
            "queue_is_source_for_next_job": self._obter_verificacao_operacional_pronta(run_id=run.id) is not None,
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

    def _obter_verificacao_operacional_pronta(self, *, run_id: int | None = None) -> BlockVerificationRun | None:
        today = timezone.localdate()
        qs = BlockVerificationRun.objects.prefetch_related("items").filter(
            status=BlockVerificationRun.STATUS_SUCCESS,
            finished_at__isnull=False,
            started_at__date=today,
        )
        if run_id is not None:
            return qs.filter(pk=run_id).first()
        return qs.first()

    def _processar_fila_verificacao_operacional(
        self,
        verification_run: BlockVerificationRun,
        *,
        result: BlockServiceResult,
        dry_run: bool,
    ) -> BlockServiceResult:
        for item in verification_run.items.filter(acao_final="BLOQUEAR").order_by("colaborador_nome", "usuario_ad"):
            outcome = self.processar_usuario_bloqueio(
                self._ferias_from_verification_item(item),
                dry_run=dry_run,
            )
            self._acumular_resultado(result, outcome, acao="BLOQUEIO")

        for item in verification_run.items.filter(acao_final="DESBLOQUEAR").order_by("colaborador_nome", "usuario_ad"):
            outcome = self.processar_usuario_desbloqueio(
                self._ferias_from_verification_item(item),
                dry_run=dry_run,
            )
            self._acumular_resultado(result, outcome, acao="DESBLOQUEIO")

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

    def processar_bloqueios(self, result: BlockServiceResult, *, dry_run: bool = False) -> BlockServiceResult:
        seen_collaborators: set[int] = set()
        for ferias in self.repository.buscar_para_bloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            outcome = self.processar_usuario_bloqueio(ferias, dry_run=dry_run)
            self._acumular_resultado(result, outcome, acao="BLOQUEIO")
        return result

    def processar_desbloqueios(self, result: BlockServiceResult, *, dry_run: bool = False) -> BlockServiceResult:
        seen_collaborators: set[int] = set()
        for ferias in self.repository.buscar_para_desbloqueio_hoje():
            if ferias.colaborador_id in seen_collaborators:
                continue
            seen_collaborators.add(ferias.colaborador_id)
            outcome = self.processar_usuario_desbloqueio(ferias, dry_run=dry_run)
            self._acumular_resultado(result, outcome, acao="DESBLOQUEIO")
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
            # A regra da VPN depende do grupo Printi_Acesso retornado pelo PowerShell.
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
            # Se o usuário ainda pertence ao grupo Printi_Acesso, a VPN volta com o AD.
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
        rows: list[dict] = []
        seen_block: set[int] = set()
        for ferias in self.repository.buscar_para_bloqueio_hoje():
            if ferias.colaborador_id in seen_block:
                continue
            seen_block.add(ferias.colaborador_id)
            rows.append(self._build_verification_candidate(ferias, acao_inicial="BLOQUEAR"))

        seen_unlock: set[int] = set()
        for ferias in self.repository.buscar_para_desbloqueio_hoje():
            if ferias.colaborador_id in seen_unlock:
                continue
            seen_unlock.add(ferias.colaborador_id)
            rows.append(self._build_verification_candidate(ferias, acao_inicial="DESBLOQUEAR"))
        return rows

    def _build_verification_candidate(self, ferias, *, acao_inicial: str) -> dict:
        collaborator = ferias.colaborador
        ad_status = self.repository.obter_status_ad(collaborator.id)
        vpn_status = self.repository.obter_status_vpn(collaborator.id)
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
            "motivo_inicial": motivo_inicial,
        }

    def _process_verification_candidate(self, item: dict, *, ad_lookup: dict[str, dict]) -> dict:
        candidate = dict(item)
        acao_inicial = candidate["acao_inicial"]
        colaborador_id = candidate["colaborador_id"]
        ad_status_banco = candidate["ad_status_banco_antes"]
        vpn_status_banco = candidate["vpn_status_banco_antes"]

        if self.repository.ja_processado_hoje(colaborador_id, "BLOQUEIO" if acao_inicial == "BLOQUEAR" else "DESBLOQUEIO"):
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_REMOVED,
                ad_status_real=ad_status_banco,
                vpn_status_real=vpn_status_banco,
                ad_status_banco_depois=ad_status_banco,
                vpn_status_banco_depois=vpn_status_banco,
                motivo="Já processado hoje com sucesso.",
            )
            return candidate

        ad_real = ad_lookup.get(candidate["usuario_ad"].strip().lower()) or self._error_consulta_operacional(
            candidate["usuario_ad"],
            "Usuário não retornado pela consulta em lote.",
        )
        candidate["ad_status_real"] = ad_real.get("ad_status", "ERRO")
        candidate["vpn_status_real"] = ad_real.get("vpn_status", "NP")

        if not ad_real.get("success"):
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_ERROR,
                ad_status_banco_depois=ad_status_banco,
                vpn_status_banco_depois=vpn_status_banco,
                motivo=f"Falha ao validar no AD: {ad_real.get('message', 'Sem detalhe')}",
            )
            return candidate

        ad_real_normalizado = self._normalizar_status_ad(ad_real.get("ad_status") or "")
        ad_banco_normalizado = self._normalizar_status_ad(ad_status_banco)
        if acao_inicial == "BLOQUEAR":
            if ad_real_normalizado == "BLOQUEADO":
                self.repository.atualizar_status_block(
                    colaborador_id=colaborador_id,
                    ad_status=ad_real.get("ad_status", "BLOQUEADO"),
                    vpn_status=ad_real.get("vpn_status", "NP"),
                )
                candidate.update(
                    acao_final="IGNORAR",
                    resultado_verificacao=BlockVerificationItem.OUTCOME_SYNCED,
                    ad_status_banco_depois=ad_real.get("ad_status", "BLOQUEADO"),
                    vpn_status_banco_depois=ad_real.get("vpn_status", "NP"),
                    motivo=(
                        f"Lista inicial pedia bloqueio, mas o AD já estava bloqueado. "
                        f"Status local era {ad_banco_normalizado or 'VAZIO'} e foi sincronizado."
                    ),
                )
                return candidate

            candidate.update(
                acao_final="BLOQUEAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_KEPT,
                ad_status_banco_depois=ad_status_banco,
                vpn_status_banco_depois=vpn_status_banco,
                motivo=f"Mantido na fila final. {candidate['motivo_inicial']}",
            )
            return candidate

        if ad_real_normalizado == "LIBERADO":
            self.repository.atualizar_status_block(
                colaborador_id=colaborador_id,
                ad_status=ad_real.get("ad_status", "LIBERADO"),
                vpn_status=ad_real.get("vpn_status", "NP"),
            )
            candidate.update(
                acao_final="IGNORAR",
                resultado_verificacao=BlockVerificationItem.OUTCOME_SYNCED,
                ad_status_banco_depois=ad_real.get("ad_status", "LIBERADO"),
                vpn_status_banco_depois=ad_real.get("vpn_status", "NP"),
                motivo=(
                    f"Lista inicial pedia desbloqueio, mas o AD já estava liberado. "
                    f"Status local era {ad_banco_normalizado or 'VAZIO'} e foi sincronizado."
                ),
            )
            return candidate

        candidate.update(
            acao_final="DESBLOQUEAR",
            resultado_verificacao=BlockVerificationItem.OUTCOME_KEPT,
            ad_status_banco_depois=ad_status_banco,
            vpn_status_banco_depois=vpn_status_banco,
            motivo=f"Mantido na fila final. {candidate['motivo_inicial']}",
        )
        return candidate

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

    def _create_verification_item(self, run: BlockVerificationRun, item: dict) -> None:
        BlockVerificationItem.objects.create(
            run=run,
            colaborador_id=item["colaborador_id"],
            colaborador_nome=item["colaborador_nome"],
            usuario_ad=item["usuario_ad"],
            email=item["email"],
            data_saida=item["data_saida"],
            data_retorno=item["data_retorno"],
            acao_inicial=item["acao_inicial"],
            acao_final=item["acao_final"],
            resultado_verificacao=item["resultado_verificacao"],
            ad_status_banco_antes=item["ad_status_banco_antes"],
            vpn_status_banco_antes=item["vpn_status_banco_antes"],
            ad_status_real=item.get("ad_status_real", ""),
            vpn_status_real=item.get("vpn_status_real", ""),
            ad_status_banco_depois=item.get("ad_status_banco_depois", ""),
            vpn_status_banco_depois=item.get("vpn_status_banco_depois", ""),
            motivo=item.get("motivo", ""),
        )

    def _motivo_inicial_verificacao(self, ferias, *, acao_inicial: str) -> str:
        today = timezone.localdate()
        if acao_inicial == "BLOQUEAR":
            return "Saindo de férias hoje." if ferias.data_saida == today else "Em férias e ainda não bloqueado."
        return "Retornando de férias hoje." if ferias.data_retorno == today else "Já retornou e ainda está bloqueado."

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

    def dashboard_data(self) -> dict:
        today = timezone.localdate()
        config = self.repository.obter_configuracao_ativa_block()
        latest_verification_run = BlockVerificationRun.objects.prefetch_related("items").first()
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
            "ultimas_verificacoes": list(BlockVerificationRun.objects.all()[:5]),
            "itens_ultima_verificacao": list(latest_verification_run.items.all()[:20]) if latest_verification_run else [],
            "ultima_verificacao": latest_verification_run,
        }

    def dashboard_data_filtrada(self, *, reference=None) -> dict:
        today = timezone.localdate()
        reference = reference or f"{today.year:04d}-{today.month:02d}"
        return_year, return_month = self._parse_reference(reference)
        config = self.repository.obter_configuracao_ativa_block()
        latest_verification_run = BlockVerificationRun.objects.prefetch_related("items").first()
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
