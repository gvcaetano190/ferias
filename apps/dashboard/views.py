from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.dashboard.services import DashboardService


@login_required
def home(request):
    service = DashboardService()
    period = service.resolve_period(request.GET.get("period"))
    status = service.resolve_status(request.GET.get("status"))
    context = service.summary(period, status, request.GET.get("return_date"))
    if request.headers.get("HX-Request") and request.GET.get("partial") == "table":
        template = "dashboard/partials/period_table.html"
    else:
        template = "dashboard/partials/period_panel.html" if request.headers.get("HX-Request") else "dashboard/home.html"
    return render(request, template, context)
