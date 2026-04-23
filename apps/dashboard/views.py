from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.dashboard.services import DashboardService


@login_required
def home(request):
    service = DashboardService()
    period = service.resolve_period(request.GET.get("period"))
    context = service.summary(period)
    template = "dashboard/partials/period_panel.html" if request.headers.get("HX-Request") else "dashboard/home.html"
    return render(request, template, context)
