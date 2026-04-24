from __future__ import annotations

from dataclasses import dataclass

from apps.block.repositories import BlockRepository
from integrations.ad.executor import bloquear_usuario_ad, desbloquear_usuario_ad


@dataclass
class BlockServiceResult:
    bloqueios_feitos: int = 0
    desbloqueios_feitos: int = 0
    erros: int = 0
    ignorados: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "bloqueios_feitos": self.bloqueios_feitos,
            "desbloqueios_feitos": self.desbloqueios_feitos,
            "erros": self.erros,
            "ignorados": self.ignorados,
        }


class BlockService:
    def __init__(self):
        self.repository = BlockRepository()

    def processar_verificacao_block(self) -> dict:
        result = BlockServiceResult()
        result = self.processar_bloqueios(result)
        result = self.processar_desbloqueios(result)
        return result.as_dict()

    def processar_bloqueios(self, result: BlockServiceResult) -> BlockServiceResult:
        for ferias in self.repository.buscar_para_bloqueio_hoje():
            outcome = self.processar_usuario_bloqueio(ferias)
            self._acumular_resultado(result, outcome, acao="BLOQUEIO")
        return result

    def processar_desbloqueios(self, result: BlockServiceResult) -> BlockServiceResult:
        for ferias in self.repository.buscar_para_desbloqueio_hoje():
            outcome = self.processar_usuario_desbloqueio(ferias)
            self._acumular_resultado(result, outcome, acao="DESBLOQUEIO")
        return result

    def processar_usuario_bloqueio(self, ferias) -> dict:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        if not self.repository.pode_bloquear(collaborator.id):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="BLOQUEIO",
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
                ad_status="IGNORADO",
                vpn_status="IGNORADO",
                resultado="IGNORADO",
                mensagem="Bloqueio já executado com sucesso hoje.",
            )
            return {"resultado": "IGNORADO"}

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
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return {"resultado": resultado}

    def processar_usuario_desbloqueio(self, ferias) -> dict:
        collaborator = ferias.colaborador
        ad_status_atual = self.repository.obter_status_ad(collaborator.id)
        if not self.repository.pode_desbloquear(collaborator.id):
            self.repository.salvar_resultado_execucao(
                colaborador_id=collaborator.id,
                usuario_ad=collaborator.login_ad or "",
                email=collaborator.email or "",
                acao="DESBLOQUEIO",
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
                ad_status="IGNORADO",
                vpn_status="NP",
                resultado="IGNORADO",
                mensagem="Desbloqueio já executado com sucesso hoje.",
            )
            return {"resultado": "IGNORADO"}

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
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return {"resultado": resultado}

    def dashboard_data(self) -> dict:
        config = self.repository.obter_configuracao_ativa_block()
        return {
            "resumo": self.repository.resumo_dashboard_block(),
            "ultimos_processamentos": self.repository.listar_ultimos_processamentos(),
            "configuracao_ativa": config,
            "usuario_teste_atual": self.repository.obter_usuario_teste_block(),
        }

    def testar_bloqueio(self) -> dict:
        usuario_teste = self.repository.obter_usuario_teste_block()
        if not usuario_teste:
            raise ValueError("Nenhum usuário de teste configurado no admin.")

        ad_result = bloquear_usuario_ad(usuario_teste)
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"
        self.repository.salvar_resultado_execucao(
            colaborador_id=0,
            usuario_ad=ad_result.get("usuario_ad") or usuario_teste,
            email="",
            acao="BLOQUEIO_TESTE",
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

        ad_result = desbloquear_usuario_ad(usuario_teste)
        resultado = "SUCESSO" if ad_result.get("success") else "ERRO"
        self.repository.salvar_resultado_execucao(
            colaborador_id=0,
            usuario_ad=ad_result.get("usuario_ad") or usuario_teste,
            email="",
            acao="DESBLOQUEIO_TESTE",
            ad_status=ad_result.get("ad_status", "ERRO"),
            vpn_status=ad_result.get("vpn_status", "NP"),
            resultado=resultado,
            mensagem=ad_result.get("message", ""),
        )
        return ad_result

    def _acumular_resultado(self, result: BlockServiceResult, outcome: dict, *, acao: str) -> None:
        resultado = outcome.get("resultado")
        if resultado == "SUCESSO" and acao == "BLOQUEIO":
            result.bloqueios_feitos += 1
        elif resultado == "SUCESSO" and acao == "DESBLOQUEIO":
            result.desbloqueios_feitos += 1
        elif resultado == "IGNORADO":
            result.ignorados += 1
        else:
            result.erros += 1
