from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.people.models import Ferias
from apps.shared.services.sync import SpreadsheetSyncService


class Command(BaseCommand):
    help = "Alinha data_saida/data_retorno com o mês/ano de referência já gravados."

    def handle(self, *args, **options):
        service = SpreadsheetSyncService()
        updated = 0
        removed_duplicates = 0

        for item in Ferias.objects.exclude(ano_ref__isnull=True).exclude(mes_ref__isnull=True):
            start = service.normalize_date(item.data_saida, item.mes_ref, item.ano_ref)
            end = service.normalize_return_date(item.data_retorno, start)

            if start == item.data_saida and end == item.data_retorno:
                continue

            duplicate_exists = Ferias.objects.exclude(pk=item.pk).filter(
                colaborador_id=item.colaborador_id,
                data_saida=start,
                data_retorno=end,
                mes_ref=item.mes_ref,
                ano_ref=item.ano_ref,
            ).exists()

            if duplicate_exists:
                item.delete()
                removed_duplicates += 1
                continue

            item.data_saida = start
            item.data_retorno = end
            item.save(update_fields=["data_saida", "data_retorno"])
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Registros corrigidos: {updated}; duplicados removidos: {removed_duplicates}"
            )
        )
