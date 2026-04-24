from __future__ import annotations

from django.utils import timezone

from apps.passwords.models import PasswordLink


class PasswordLinkRepository:
    def recent(self, limit: int = 15, query: str = ""):
        queryset = PasswordLink.objects.order_by("-criado_em", "-id")
        if query:
            queryset = queryset.filter(nome_pessoa__icontains=query) | queryset.filter(gestor_pessoa__icontains=query)
            queryset = queryset.order_by("-criado_em", "-id")
        return queryset[:limit]

    def get(self, pk: int) -> PasswordLink | None:
        try:
            return PasswordLink.objects.get(pk=pk)
        except PasswordLink.DoesNotExist:
            return None

    def create(self, **kwargs) -> PasswordLink:
        kwargs.setdefault("criado_em", timezone.now())
        return PasswordLink.objects.create(**kwargs)

    def mark_viewed(self, pk: int) -> None:
        PasswordLink.objects.filter(pk=pk).update(visualizado=True)

    def mark_expired(self, pk: int) -> None:
        PasswordLink.objects.filter(pk=pk, expirado_em__isnull=True).update(expirado_em=timezone.now())
