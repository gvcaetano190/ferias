from __future__ import annotations

from django.utils import timezone

from apps.people.models import SyncLog


class SyncLogRepository:
    def latest(self) -> SyncLog | None:
        return SyncLog.objects.order_by("-created_at").first()

    def latest_by_type(self, sync_type: str) -> SyncLog | None:
        return SyncLog.objects.filter(tipo_sync=sync_type).order_by("-created_at").first()

    def create(
        self,
        *,
        tipo_sync: str,
        status: str,
        total_registros: int = 0,
        total_abas: int = 0,
        mensagem: str = "",
        arquivo_hash: str | None = None,
        detalhes: str | None = None,
    ) -> SyncLog:
        return SyncLog.objects.create(
            tipo_sync=tipo_sync,
            status=status,
            total_registros=total_registros,
            total_abas=total_abas,
            mensagem=mensagem,
            arquivo_hash=arquivo_hash,
            detalhes=detalhes,
            created_at=timezone.now(),
        )
