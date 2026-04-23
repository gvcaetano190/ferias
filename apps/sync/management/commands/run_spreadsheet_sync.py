from django.core.management.base import BaseCommand

from apps.sync.services import SpreadsheetSyncService


class Command(BaseCommand):
    help = "Baixa a planilha, processa os dados e atualiza as tabelas operacionais."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Força um novo download do arquivo.")

    def handle(self, *args, **options):
        result = SpreadsheetSyncService().run(force=options["force"])
        self.stdout.write(f"{result.get('status')}: {result.get('message')}")
