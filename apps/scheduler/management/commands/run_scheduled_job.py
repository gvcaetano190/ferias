from django.core.management.base import BaseCommand, CommandError

from apps.scheduler.services import SchedulerService


class Command(BaseCommand):
    help = "Executa um job específico do scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)

    def handle(self, *args, **options):
        service = SchedulerService()
        job = service.repository.get_job(options["job_id"])
        if not job:
            raise CommandError("Job não encontrado.")
        result = service.run_job(job)
        self.stdout.write(self.style.SUCCESS(f"{job.name}: {result.message}"))

