from __future__ import annotations

import argparse
import os
import sys
from contextlib import ExitStack
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project.settings")

import django

django.setup()

from django.utils import timezone

from apps.block.models import BlockConfig, BlockProcessing
from apps.block.services import BlockService
from apps.people.models import Acesso, Colaborador, Ferias


USUARIO_AD_TESTE = "teste-infra"
NOME_TESTE = "Usuario Teste Infra"
EMAIL_TESTE = "teste-infra@teste.local"
AD_SYSTEM_NAME = "AD PRIN"
VPN_SYSTEM_NAME = "VPN"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Homologacao controlada do modulo block.")
    parser.add_argument(
        "--cenario",
        required=True,
        choices=("saida-hoje", "retorno-hoje", "ferias-atrasado", "retorno-atrasado"),
        help="Cenario de negocio a preparar.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Usa respostas mockadas do executor AD. Este e o modo recomendado.",
    )
    parser.add_argument(
        "--real-ad",
        action="store_true",
        help="Permite consultar e executar no AD real. Use com cautela.",
    )
    parser.add_argument(
        "--usuario-ad",
        default=USUARIO_AD_TESTE,
        help="Usuario AD tecnico usado na homologacao.",
    )
    return parser.parse_args()


def scenario_dates(cenario: str):
    hoje = timezone.localdate()
    if cenario == "saida-hoje":
        return hoje, hoje + timedelta(days=5)
    if cenario == "retorno-hoje":
        return hoje - timedelta(days=5), hoje
    if cenario == "ferias-atrasado":
        return hoje - timedelta(days=2), hoje + timedelta(days=3)
    if cenario == "retorno-atrasado":
        return hoje - timedelta(days=8), hoje - timedelta(days=1)
    raise ValueError(f"Cenario invalido: {cenario}")


def initial_statuses(cenario: str):
    if cenario in {"saida-hoje", "ferias-atrasado"}:
        return "LIBERADO", "LIBERADA"
    return "BLOQUEADO", "BLOQUEADA"


def ensure_colaborador(usuario_ad: str) -> Colaborador:
    colaborador, _ = Colaborador.objects.update_or_create(
        login_ad=usuario_ad,
        defaults={
            "nome": NOME_TESTE,
            "email": EMAIL_TESTE,
            "ativo": True,
        },
    )
    return colaborador


def ensure_ferias(colaborador: Colaborador, *, data_saida, data_retorno) -> Ferias:
    Ferias.objects.filter(colaborador=colaborador).delete()
    return Ferias.objects.create(
        colaborador=colaborador,
        data_saida=data_saida,
        data_retorno=data_retorno,
        mes_ref=data_retorno.month,
        ano_ref=data_retorno.year,
    )


def ensure_acesso(colaborador: Colaborador, *, sistema: str, status: str) -> Acesso:
    acesso, _ = Acesso.objects.update_or_create(
        colaborador=colaborador,
        sistema=sistema,
        defaults={"status": status},
    )
    return acesso


def ensure_block_config(usuario_ad: str):
    BlockConfig.objects.update_or_create(
        ativo=True,
        defaults={
            "nome": "Homologacao Block",
            "usuario_teste_ad": usuario_ad,
            "dry_run": False,
        },
    )


def prepare_data(cenario: str, usuario_ad: str):
    data_saida, data_retorno = scenario_dates(cenario)
    status_ad, status_vpn = initial_statuses(cenario)
    colaborador = ensure_colaborador(usuario_ad)
    ferias = ensure_ferias(
        colaborador,
        data_saida=data_saida,
        data_retorno=data_retorno,
    )
    ensure_acesso(colaborador, sistema=AD_SYSTEM_NAME, status=status_ad)
    ensure_acesso(colaborador, sistema=VPN_SYSTEM_NAME, status=status_vpn)
    ensure_block_config(usuario_ad)
    BlockProcessing.objects.filter(colaborador_id=colaborador.id).delete()
    return colaborador, ferias


def mock_payloads(cenario: str, usuario_ad: str) -> tuple[dict, dict]:
    if cenario in {"saida-hoje", "ferias-atrasado"}:
        consulta = {
            "success": True,
            "usuario_ad": usuario_ad,
            "user_found": True,
            "ad_status": "LIBERADO",
            "vpn_status": "LIBERADA",
            "message": "Consulta AD realizada com sucesso",
            "is_enabled": True,
            "is_in_printi_acesso": True,
            "already_in_desired_state": False,
        }
        acao = {
            "success": True,
            "usuario_ad": usuario_ad,
            "user_found": True,
            "is_in_printi_acesso": True,
            "ad_status": "BLOQUEADO",
            "vpn_status": "BLOQUEADA",
            "message": "Usuario bloqueado com sucesso",
            "already_in_desired_state": False,
        }
        return consulta, acao

    consulta = {
        "success": True,
        "usuario_ad": usuario_ad,
        "user_found": True,
        "ad_status": "BLOQUEADO",
        "vpn_status": "BLOQUEADA",
        "message": "Consulta AD realizada com sucesso",
        "is_enabled": False,
        "is_in_printi_acesso": True,
        "already_in_desired_state": False,
    }
    acao = {
        "success": True,
        "usuario_ad": usuario_ad,
        "user_found": True,
        "is_in_printi_acesso": False,
        "ad_status": "LIBERADO",
        "vpn_status": "NP",
        "message": "Usuario desbloqueado com sucesso",
        "already_in_desired_state": False,
    }
    return consulta, acao


def run_flow(cenario: str, usuario_ad: str, *, use_real_ad: bool):
    _, ferias = prepare_data(cenario, usuario_ad)
    service = BlockService()
    acao = "BLOQUEIO" if cenario in {"saida-hoje", "ferias-atrasado"} else "DESBLOQUEIO"

    if use_real_ad:
        return execute_single_flow(service, ferias, acao)

    consulta_payload, acao_payload = mock_payloads(cenario, usuario_ad)
    with ExitStack() as stack:
        stack.enter_context(patch("apps.block.services.consultar_usuario_ad", return_value=consulta_payload))
        if acao == "BLOQUEIO":
            stack.enter_context(patch("apps.block.services.bloquear_usuario_ad", return_value=acao_payload))
        else:
            stack.enter_context(patch("apps.block.services.desbloquear_usuario_ad", return_value=acao_payload))
        return execute_single_flow(service, ferias, acao)


def execute_single_flow(service: BlockService, ferias: Ferias, acao: str) -> dict:
    if acao == "BLOQUEIO":
        outcome = service.processar_usuario_bloqueio(ferias)
        return {
            "bloqueios_feitos": 1 if outcome.get("resultado") == "SUCESSO" else 0,
            "desbloqueios_feitos": 0,
            "sincronizados": 1 if outcome.get("resultado") == "SINCRONIZADO" else 0,
            "erros": 1 if outcome.get("resultado") == "ERRO" else 0,
            "ignorados": 1 if outcome.get("resultado") == "IGNORADO" else 0,
        }

    outcome = service.processar_usuario_desbloqueio(ferias)
    return {
        "bloqueios_feitos": 0,
        "desbloqueios_feitos": 1 if outcome.get("resultado") == "SUCESSO" else 0,
        "sincronizados": 1 if outcome.get("resultado") == "SINCRONIZADO" else 0,
        "erros": 1 if outcome.get("resultado") == "ERRO" else 0,
        "ignorados": 1 if outcome.get("resultado") == "IGNORADO" else 0,
    }


def print_summary(usuario_ad: str, resumo: dict):
    colaborador = Colaborador.objects.get(login_ad=usuario_ad)
    acessos = {
        item.sistema: item.status
        for item in Acesso.objects.filter(colaborador=colaborador)
    }
    processamentos = list(
        BlockProcessing.objects.filter(colaborador_id=colaborador.id).order_by("-executado_em")[:5]
    )

    print("Resumo da execucao")
    print(f"Usuario AD: {usuario_ad}")
    print(f"Bloqueios: {resumo.get('bloqueios_feitos', 0)}")
    print(f"Desbloqueios: {resumo.get('desbloqueios_feitos', 0)}")
    print(f"Sincronizados: {resumo.get('sincronizados', 0)}")
    print(f"Erros: {resumo.get('erros', 0)}")
    print(f"Ignorados: {resumo.get('ignorados', 0)}")
    print("")
    print("Status atuais no banco")
    print(f"AD PRIN: {acessos.get(AD_SYSTEM_NAME, '-')}")
    print(f"VPN: {acessos.get(VPN_SYSTEM_NAME, '-')}")
    print("")
    print("Ultimos logs em block_processings")
    for item in processamentos:
        print(
            f"- {item.executado_em:%Y-%m-%d %H:%M:%S} | {item.acao} | {item.resultado} | "
            f"AD={item.ad_status} | VPN={item.vpn_status} | {item.mensagem}"
        )


def main():
    args = parse_args()
    if args.real_ad and args.mock:
        raise SystemExit("Use apenas uma opcao entre --mock e --real-ad.")
    if not args.real_ad and not args.mock:
        args.mock = True

    resumo = run_flow(
        args.cenario,
        args.usuario_ad,
        use_real_ad=args.real_ad,
    )
    print_summary(args.usuario_ad, resumo)
    if args.real_ad:
        print("")
        print("ATENCAO: esta execucao consultou e pode ter alterado o AD real.")
    else:
        print("")
        print("Modo mock: nenhum bloqueio real no AD foi executado.")


if __name__ == "__main__":
    main()
