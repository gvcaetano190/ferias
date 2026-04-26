from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.block.preview_service import BlockPreviewService
from apps.block.business_service import BlockBusinessService


def _formatar_mensagem_teste(prefixo: str, resultado: dict) -> str:
    tinha_vpn = "Sim" if resultado.get("is_in_printi_acesso") else "Não"
    return (
        f"{prefixo} para {resultado.get('usuario_ad')}. "
        f"Tinha VPN: {tinha_vpn}. "
        f"{resultado.get('message')}"
    )


@login_required
def index(request):
    service = BlockPreviewService()
    reference = request.GET.get("reference", "")
    context = service.dashboard_data_filtrada(reference=reference)
    return render(request, "block/index.html", context)


@login_required
def executar_operacional(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockBusinessService()
    try:
        resumo = service.processar_verificacao_operacional_block()
        messages.success(
            request,
            (
                "Verificação operacional concluída. "
                f"Sincronizados: {resumo['total_sincronizados']} | "
                f"Fila Final: B {resumo['total_final_bloqueio']} / D {resumo['total_final_desbloqueio']} | "
                f"Erros: {resumo['total_erros']}."
            ),
        )
    except Exception as exc:
        messages.error(request, f"Erro ao processar verificação operacional: {exc}")
    
    return redirect("block:index")


@login_required
def executar(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockBusinessService()
    resumo = service.processar_verificacao_block(require_operational_queue=True)
    
    if resumo.get("skipped"):
        messages.warning(request, resumo.get("message", "Nenhuma fila operacional foi gerada hoje. Rode a Verificação Operacional primeiro."))
        return redirect("block:index")

    messages.success(
        request,
        (
            f"{'Simulação concluída' if resumo.get('dry_run') else 'Execução Final concluída'}. "
            f"Bloqueios: {resumo['bloqueios_feitos']} | "
            f"Desbloqueios: {resumo['desbloqueios_feitos']} | "
            f"Sincronizados: {resumo['sincronizados']} | "
            f"Erros: {resumo['erros']} | "
            f"Ignorados: {resumo['ignorados']}"
        ),
    )
    return redirect("block:index")


@login_required
def preview(request):
    service = BlockPreviewService()
    context = service.previsualizar_verificacao_block()
    return render(request, "block/partials/preview_modal.html", context)


@login_required
def verification_modal(request):
    service = BlockPreviewService()
    run_id = request.GET.get("run_id")
    context = service.ver_detalhes_verificacao_operacional(
        run_id=int(run_id) if run_id and run_id.isdigit() else None
    )
    return render(request, "block/partials/verification_modal.html", context)


@login_required
def testar_bloqueio(request):
    if request.method != "POST":
        return redirect("block:index")

    service = BlockBusinessService()
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

    service = BlockBusinessService()
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
