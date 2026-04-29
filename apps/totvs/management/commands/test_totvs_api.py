from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.totvs.services import TotvsIntegrationService
from integrations.totvs.client import TotvsClientError


class Command(BaseCommand):
    help = "Testa a integracao TOTVS via GET e, opcionalmente, via PUT."

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="Login ou id do usuario no TOTVS.")
        parser.add_argument(
            "--set-active",
            choices=["true", "false"],
            help="Quando informado, executa PUT para alterar o campo active do usuario.",
        )
        parser.add_argument(
            "--show-body",
            action="store_true",
            help="Exibe o payload completo retornado pela API.",
        )

    def handle(self, *args, **options):
        identifier = options["identifier"]
        desired_active = options.get("set_active")
        show_body = bool(options.get("show_body"))
        service = TotvsIntegrationService()

        try:
            resolved = service.consultar_usuario(identifier)
        except TotvsClientError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("GET realizado com sucesso."))
        self.stdout.write(f"Usuario consultado: {resolved.username}")
        self.stdout.write(f"Id TOTVS: {resolved.user_id}")
        self.stdout.write(f"Status atual: {resolved.status}")
        if show_body:
            self.stdout.write(json.dumps(resolved.payload, indent=2, ensure_ascii=False))

        if desired_active is None:
            return

        try:
            updated = service.atualizar_status_usuario(
                identifier=identifier,
                active=(desired_active == "true"),
            )
        except TotvsClientError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("PUT realizado com sucesso."))
        self.stdout.write(f"Usuario atualizado: {updated.username}")
        self.stdout.write(f"Id TOTVS: {updated.user_id}")
        self.stdout.write(f"Novo status: {updated.status}")
        if show_body:
            self.stdout.write(json.dumps(updated.payload, indent=2, ensure_ascii=False))

