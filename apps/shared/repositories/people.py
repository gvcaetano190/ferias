from __future__ import annotations

from django.db.models import Q

from apps.people.models import Acesso, Colaborador, Ferias


class ColaboradorRepository:
    def get_by_id(self, collaborator_id: int) -> Colaborador | None:
        try:
            return Colaborador.objects.get(pk=collaborator_id)
        except Colaborador.DoesNotExist:
            return None

    def search(self, query: str, limit: int = 8) -> list[Colaborador]:
        normalized = (query or "").strip()
        if not normalized:
            return []
        return list(
            Colaborador.objects.filter(
                Q(nome__icontains=normalized)
                | Q(email__icontains=normalized)
                | Q(login_ad__icontains=normalized)
            )
            .order_by("nome")[:limit]
        )

    def active_count(self) -> int:
        return Colaborador.objects.filter(ativo=True).count()


class FeriasRepository:
    def periods(self) -> list[dict]:
        return list(
            Ferias.objects.exclude(mes_ref__isnull=True)
            .exclude(ano_ref__isnull=True)
            .values("ano_ref", "mes_ref")
            .distinct()
            .order_by("-ano_ref", "-mes_ref")
        )

    def by_period(self, year: int, month: int):
        return Ferias.objects.select_related("colaborador").filter(
            ano_ref=year,
            mes_ref=month,
        )


class AcessoRepository:
    def upsert(self, *, colaborador_id: int, sistema: str, status: str) -> tuple[Acesso, bool]:
        return Acesso.objects.update_or_create(
            colaborador_id=colaborador_id,
            sistema=sistema,
            defaults={"status": status},
        )
