from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from apps.shared.services.passwords import PasswordManagementService


class PasswordManagementServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.service = PasswordManagementService()
        self.service.collaborators = mock.Mock()

    def test_decorate_link_attaches_person_and_manager_emails(self) -> None:
        collaborator = SimpleNamespace(email="pessoa@printi.com.br", gestor="Gestor Teste")
        self.service.collaborators.get_by_name.return_value = collaborator
        self.service.collaborators.get_email_by_name.return_value = "gestor@printi.com.br"
        link = SimpleNamespace(
            nome_pessoa="Pessoa Teste",
            gestor_pessoa="Gestor Teste",
            criado_em=timezone.now(),
            expirado_em=None,
            ttl_seconds=3600,
            visualizado=False,
        )

        decorated = self.service.decorate_link(link)

        self.assertEqual(decorated.pessoa_email, "pessoa@printi.com.br")
        self.assertEqual(decorated.gestor_email, "gestor@printi.com.br")

    def test_search_collaborators_attaches_manager_email(self) -> None:
        collaborator = SimpleNamespace(
            nome="Pessoa Teste",
            email="pessoa@printi.com.br",
            gestor="Gestor Teste",
        )
        self.service.collaborators.search.return_value = [collaborator]
        self.service.collaborators.get_email_by_name.return_value = "gestor@printi.com.br"

        results = self.service.search_collaborators("pessoa")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].pessoa_email, "pessoa@printi.com.br")
        self.assertEqual(results[0].gestor_email, "gestor@printi.com.br")
