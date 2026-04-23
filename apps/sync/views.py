from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from apps.sync.forms import ManualSyncForm
from apps.sync.services import SpreadsheetSyncService


@login_required
def trigger_sync(request):
    form = ManualSyncForm(request.POST or None)
    if request.method != "POST" or not form.is_valid():
        messages.error(request, "Requisição de sincronização inválida.")
        return redirect("dashboard:home")

    try:
        service = SpreadsheetSyncService()
        result = service.run(force=form.cleaned_data["force"])
    except Exception as exc:
        messages.error(request, f"Falha na sincronização: {exc}")
        return redirect("dashboard:home")

    status = result.get("status")
    if status == "success":
        messages.success(request, result["message"])
    elif status == "skipped":
        messages.info(request, result["message"])
    elif status == "disabled":
        messages.warning(request, result["message"])
    else:
        messages.error(request, result.get("message", "Falha na sincronização."))
    return redirect("dashboard:home")
