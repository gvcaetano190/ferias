from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from apps.sync.forms import ManualSyncForm
from apps.sync.services import SpreadsheetSyncService


@login_required
def trigger_sync(request):
    redirect_to = (
        request.POST.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("dashboard:home")
    )

    form = ManualSyncForm(request.POST or None)
    if request.method != "POST" or not form.is_valid():
        messages.error(request, "Requisicao de sincronizacao invalida.")
        return redirect(redirect_to)

    try:
        service = SpreadsheetSyncService()
        result = service.run(force=form.cleaned_data["force"])
    except Exception as exc:
        messages.error(request, f"Falha na sincronizacao: {exc}")
        return redirect(redirect_to)

    status = result.get("status")
    if status == "success":
        messages.success(request, result["message"])
    elif status == "skipped":
        messages.info(request, result["message"])
    elif status == "disabled":
        messages.warning(request, result["message"])
    else:
        messages.error(request, result.get("message", "Falha na sincronizacao."))
    return redirect(redirect_to)
