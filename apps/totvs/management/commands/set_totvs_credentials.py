from __future__ import annotations

from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.totvs.credentials import TotvsCredentialStore
from apps.totvs.models import TotvsIntegrationConfig


class Command(BaseCommand):
    help = "Grava ou regrava a credencial TOTVS no cofre do sistema."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Usuario tecnico TOTVS.")
        parser.add_argument(
            "--config-id",
            type=int,
            help="Id da configuracao TOTVS. Se omitido, usa a configuracao ativa.",
        )

    def handle(self, *args, **options):
        username = str(options["username"]).strip()
        config_id = options.get("config_id")

        if config_id:
            config = TotvsIntegrationConfig.objects.filter(pk=config_id).first()
        else:
            config = TotvsIntegrationConfig.objects.filter(active=True).order_by("-updated_at").first()

        if not config:
            raise CommandError("Nenhuma configuracao TOTVS encontrada para gravar a credencial.")

        password = getpass("Senha tecnica TOTVS: ")
        confirm = getpass("Confirme a senha: ")
        if not password:
            raise CommandError("Senha nao informada.")
        if password != confirm:
            raise CommandError("As senhas informadas nao conferem.")

        store = TotvsCredentialStore()
        store.save(
            credential_key=config.credential_key,
            username=username,
            password=password,
        )

        stored = store.exists(credential_key=config.credential_key)
        if not stored:
            raise CommandError("Nao foi possivel confirmar a gravacao da credencial no cofre.")

        self.stdout.write(
            self.style.SUCCESS(
                f"Credencial gravada com sucesso no cofre para a configuracao '{config.name}'."
            )
        )
