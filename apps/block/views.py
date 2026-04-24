from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.block.services import BlockService


def _formatar_mensagem_teste(prefixo: str, resultado: dict) -> str:
    tinha_vpn = "Sim" if resultado.get("is_in_printi_acesso") else "Não"
    return (
        f"{prefixo} para {resultado.get('usuario_ad')}. "
        f"Tinha VPN: {tinha_vpn}. "
        f"{resultado.get('message')}"
    )


@login_required
def index(request):
    service = BlockService()
    reference = request.GET.get("reference", "")
    context = service.dashboard_data_filtrada(reference=reference)
    return render(request, "block/index.html", context)


@login_required
def executar(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockService()
    resumo = service.processar_verificacao_block()
    messages.success(
        request,
        (
            f"{'Simulação concluída' if resumo.get('dry_run') else 'Verificação concluída'}. "
            f"Bloqueios: {resumo['bloqueios_feitos']} | "
            f"Desbloqueios: {resumo['desbloqueios_feitos']} | "
            f"Erros: {resumo['erros']} | "
            f"Ignorados: {resumo['ignorados']}"
        ),
    )
    return redirect("block:index")


@login_required
def preview(request):
    service = BlockService()
    context = service.previsualizar_verificacao_block()
    return render(request, "block/partials/preview_modal.html", context)


@login_required
def testar_bloqueio(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockService()
    try:
        resultado = service.testar_bloqueio()
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("block:index")

    if resultado.get("success"):
        messages.success(
            request,
            _formatar_mensagem_teste("Teste de bloqueio executado com sucesso", resultado),
        )
    else:
        messages.error(
            request,
            _formatar_mensagem_teste("Falha no teste de bloqueio", resultado),
        )
    return redirect("block:index")


@login_required
def testar_desbloqueio(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockService()
    try:
        resultado = service.testar_desbloqueio()
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("block:index")

    if resultado.get("success"):
        messages.success(
            request,
            _formatar_mensagem_teste("Teste de desbloqueio executado com sucesso", resultado),
        )
    else:
        messages.error(
            request,
            _formatar_mensagem_teste("Falha no teste de desbloqueio", resultado),
        )
    return redirect("block:index")
