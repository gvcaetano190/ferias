from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.conf import settings
from .services import ReportService


def _build_dashboard_context(month, year, period):
    service = ReportService()
    dept_data = service.get_department_impact_data(month=month, year=year)
    pico_data = service.get_vacation_pico_data(month=month, year=year)
    summary = service.get_period_summary(month=month, year=year)
    periods = service.get_available_periods()

    # Resolve o rótulo legível do período selecionado (ex: "Abril 2026")
    period_label = "Próximos 6 meses"
    if month and year:
        for p in periods:
            if p["month"] == month and p["year"] == year:
                period_label = p["label"]
                break

    return {
        "pico_data": pico_data,
        "dept_data": dept_data,
        "total_saiu": summary["total_saiu"],
        "ja_voltou": summary["ja_voltou"],
        "ainda_fora": summary["ainda_fora"],
        "periods": periods,
        "selected_period": period,
        "period_label": period_label,
    }


@login_required
def dashboard(request):
    period = request.GET.get("period")
    month, year = None, None
    if period and "_" in period:
        month, year = map(int, period.split("_"))

    context = _build_dashboard_context(month, year, period)

    if request.headers.get("HX-Request"):
        return render(request, "reports/partials/dashboard_content.html", context)

    return render(request, "reports/dashboard.html", context)


def dashboard_print(request):
    """
    View especial para geração de screenshot via Playwright.
    Não exige login, mas valida um token secreto na query string.
    Acesse: /relatorios/print/?period=4_2026&token=SEU_TOKEN
    """
    token = request.GET.get("token", "")
    if not token or token != settings.DASHBOARD_SCREENSHOT_TOKEN:
        return HttpResponseForbidden("Token inválido.")

    period = request.GET.get("period")
    month, year = None, None
    if period and "_" in period:
        month, year = map(int, period.split("_"))

    context = _build_dashboard_context(month, year, period)
    # Marca para o template suprimir o header/nav de navegação
    context["print_mode"] = True
    return render(request, "reports/dashboard_print.html", context)
