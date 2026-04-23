from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.block.services import BlockService


@login_required
def index(request):
    service = BlockService()
    context = service.dashboard_data()
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
            f"Verificação concluída. "
            f"Bloqueios: {resumo['bloqueios_feitos']} | "
            f"Desbloqueios: {resumo['desbloqueios_feitos']} | "
            f"Erros: {resumo['erros']} | "
            f"Ignorados: {resumo['ignorados']}"
        ),
    )
    return redirect("block:index")


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
            f"Teste de bloqueio executado com sucesso para {resultado.get('usuario_ad')}: {resultado.get('message')}",
        )
    else:
        messages.error(
            request,
            f"Falha no teste de bloqueio para {resultado.get('usuario_ad')}: {resultado.get('message')}",
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
            f"Teste de desbloqueio executado com sucesso para {resultado.get('usuario_ad')}: {resultado.get('message')}",
        )
    else:
        messages.error(
            request,
            f"Falha no teste de desbloqueio para {resultado.get('usuario_ad')}: {resultado.get('message')}",
        )
    return redirect("block:index")
