from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView

from apps.passwords.forms import PasswordShareForm
from apps.passwords.models import PasswordLink
from apps.shared.services.passwords import PasswordManagementService


class PasswordListCreateView(LoginRequiredMixin, FormView):
    form_class = PasswordShareForm
    template_name = "passwords/index.html"
    success_url = reverse_lazy("passwords:index")
    password_service = PasswordManagementService()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_links"] = self.password_service.recent_links(limit=15)
        return context

    def form_valid(self, form):
        try:
            self.password_service.create_link(
                collaborator_id=int(form.cleaned_data["colaborador_id"]),
                senha=form.cleaned_data["senha"],
                descricao=form.cleaned_data["descricao"],
                ttl_seconds=int(form.cleaned_data["ttl_seconds"]),
                username=self.request.user.get_username(),
            )
        except ValueError as exc:
            messages.error(self.request, str(exc))
            return redirect(self.success_url)
        messages.success(self.request, "Link seguro criado com sucesso.")
        return redirect(self.success_url)


@login_required
def check_password_status(request, pk: int):
    password_service = PasswordManagementService()
    try:
        password_link, result = password_service.check_status(pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("passwords:index")

    if result["viewed"]:
        messages.success(request, "O link já foi visualizado.")
    else:
        messages.info(request, f"Status atual: {result['raw_state']}.")

    return redirect("passwords:index")


@login_required
def collaborator_lookup(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    collaborators = PasswordManagementService().search_collaborators(query, limit=8) if query else []

    return render(
        request,
        "passwords/partials/collaborator_results.html",
        {
            "collaborators": collaborators,
            "query": query,
        },
    )
