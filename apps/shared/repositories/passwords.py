from __future__ import annotations

from apps.passwords.models import PasswordLink


class PasswordLinkRepository:
    def recent(self, limit: int = 15):
        return PasswordLink.objects.all()[:limit]

    def get(self, pk: int) -> PasswordLink | None:
        try:
            return PasswordLink.objects.get(pk=pk)
        except PasswordLink.DoesNotExist:
            return None

    def create(self, **kwargs) -> PasswordLink:
        return PasswordLink.objects.create(**kwargs)

    def mark_viewed(self, pk: int) -> None:
        PasswordLink.objects.filter(pk=pk).update(visualizado=True)
