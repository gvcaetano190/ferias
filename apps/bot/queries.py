"""
BotQueryService
===============
Consultas ao banco de dados disparadas pelos comandos do bot WhatsApp.
"""
from __future__ import annotations

from datetime import date


class BotQueryService:
    def localizar_colaborador(self, termo: str):
        from django.db.models import Q
        from apps.people.models import Colaborador

        termo = (termo or "").strip()
        if not termo:
            return None

        return (
            Colaborador.objects.filter(
                Q(nome__icontains=termo)
                | Q(email__icontains=termo)
                | Q(login_ad__icontains=termo)
            )
            .order_by("nome")
            .first()
        )

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

    def buscar_colaborador(self, termo: str) -> dict | None:
        """Busca os detalhes 360 de um colaborador por nome ou email."""
        colab = self.localizar_colaborador(termo)
        if not colab:
            return None
            
        # Pegar próximas férias ou férias atuais
        hoje = date.today()
        proximas_ferias = colab.ferias_registros.filter(
            data_retorno__gte=hoje
        ).order_by("data_saida").first()
        
        # Pegar status de acesso
        acessos = colab.acessos_registros.all()
        status_vpn = next((a.status for a in acessos if a.sistema == "VPN"), "—")
        status_ad = next((a.status for a in acessos if a.sistema == "AD PRIN"), "—")
        
        return {
            "nome": colab.nome,
            "email": colab.email,
            "login_ad": colab.login_ad,
            "departamento": colab.departamento,
            "gestor": colab.gestor,
            "ferias_saida": proximas_ferias.data_saida if proximas_ferias else None,
            "ferias_retorno": proximas_ferias.data_retorno if proximas_ferias else None,
            "status_vpn": status_vpn,
            "status_ad": status_ad,
        }

    def buscar_gestor(self, termo: str) -> dict | None:
        """Busca o gestor (nome e email) de um colaborador."""
        from django.db.models import Q
        from apps.people.models import Colaborador
        
        termo = termo.strip()
        if not termo:
            return None
            
        colab = Colaborador.objects.filter(
            Q(nome__icontains=termo) | Q(email__icontains=termo)
        ).first()
        
        if not colab or not colab.gestor:
            return None
            
        # Tenta achar o email do gestor na própria base
        gestor_obj = Colaborador.objects.filter(nome__icontains=colab.gestor).first()
        gestor_email = gestor_obj.email if gestor_obj else "Não encontrado no sistema"
        
        return {
            "colaborador_nome": colab.nome,
            "gestor_nome": colab.gestor,
            "gestor_email": gestor_email
        }
