from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
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
        history_query = (self.request.GET.get("history_q") or "").strip()
        context["recent_links"] = self.password_service.recent_links(limit=30, query=history_query)
        context["history_query"] = history_query
        return context

    def form_valid(self, form):
        try:
            self.password_service.create_link(
                secret_payload=form.cleaned_data["secret_payload"],
                descricao=form.cleaned_data["descricao"],
                ttl_seconds=int(form.cleaned_data["ttl_seconds"]),
                username=self.request.user.get_username(),
                nome_pessoa=form.cleaned_data.get("nome_pessoa") or "",
                gestor_pessoa=form.cleaned_data.get("gestor_pessoa") or "",
                finalidade=form.cleaned_data.get("finalidade") or "Acesso Temporário",
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
        if request.headers.get("HX-Request"):
            return HttpResponse(str(exc), status=400)
        messages.error(request, str(exc))
        return redirect("passwords:index")

    if request.headers.get("HX-Request"):
        return render(request, "passwords/partials/history_card.html", {"link": password_link})

    if result["viewed"]:
        messages.success(request, "O link já foi visualizado.")
    elif result["raw_state"] == "expired":
        messages.warning(request, "O link expirou.")

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
