from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.totvs.services import TotvsIntegrationService
from integrations.totvs.client import TotvsClientError


class Command(BaseCommand):
    help = "Consulta um usuario no TOTVS e sincroniza o status do sistema TOTVS no banco local."

    def add_arguments(self, parser):
        parser.add_argument("login_ad", help="login_ad do colaborador no banco.")

    def handle(self, *args, **options):
        login_ad = str(options["login_ad"]).strip()
        service = TotvsIntegrationService()

        try:
            resolved = service.sincronizar_status_no_banco_por_login(login_ad=login_ad)
        except TotvsClientError as exc:
            raise CommandError(str(exc)) from exc

        if resolved.found:
            self.stdout.write(self.style.SUCCESS("Status TOTVS sincronizado no banco com sucesso."))
            self.stdout.write(f"Login: {resolved.username}")
            self.stdout.write(f"Id TOTVS: {resolved.user_id}")
            self.stdout.write(f"Status gravado no banco: {resolved.status}")
            return

        self.stdout.write(self.style.WARNING("Usuario nao encontrado no TOTVS."))
        self.stdout.write(f"Login: {resolved.username}")
        self.stdout.write("Status gravado no banco: NP")

