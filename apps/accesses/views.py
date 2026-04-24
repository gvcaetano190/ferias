from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accesses.services import AccessesService


@login_required
def index(request):
    service = AccessesService()
    filters = service.resolve_filters(request.GET)
    context = service.dashboard_data(filters)
    return render(request, "accesses/index.html", context)

