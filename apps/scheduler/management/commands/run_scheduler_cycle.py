from django.core.management.base import BaseCommand

from apps.scheduler.services import SchedulerService


class Command(BaseCommand):
    help = "Executa um ciclo do scheduler, rodando jobs vencidos."

    def handle(self, *args, **options):
        service = SchedulerService()
        service.ensure_default_jobs()
        results = service.run_due_jobs()
        self.stdout.write(self.style.SUCCESS(f"Jobs executados neste ciclo: {len(results)}"))
        for result in results:
            self.stdout.write(f"- {result.status}: {result.message}")

