from __future__ import annotations

import uuid
from unittest import TestCase, mock

from apps.people.models import Acesso, Colaborador
from apps.totvs.models import TotvsIntegrationConfig
from apps.totvs.services import TotvsIntegrationService
from integrations.totvs.client import TotvsClientError

from integrations.totvs.client import TotvsClient


class TotvsClientTests(TestCase):
    def setUp(self):
        self.client = TotvsClient(
            base_url="https://example.com:2007",
            tenant_id="01,01",
            username="user",
            password="secret",
        )

    @mock.patch("integrations.totvs.client.requests.Session.request")
    def test_get_user_sends_basic_headers(self, request_mock):
        response = mock.Mock()
        response.json.return_value = {"id": "000240", "userName": "infra-teste", "active": False}
        response.raise_for_status.return_value = None
        request_mock.return_value = response

        payload = self.client.get_user("infra-teste")

        self.assertEqual(payload["id"], "000240")
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["headers"]["TenantId"], "01,01")
        self.assertEqual(kwargs["auth"], ("user", "secret"))

    @mock.patch("integrations.totvs.client.requests.Session.request")
    def test_update_user_active_builds_expected_body(self, request_mock):
        response = mock.Mock()
        response.json.return_value = {"id": "000240", "userName": "infra-teste", "active": False}
        response.raise_for_status.return_value = None
        request_mock.return_value = response

        payload = {
            "schemas": [
                "urn:scim:schemas:core:2.0:User",
                "urn:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": "000240",
            "userName": "infra-teste",
            "name": {
                "formatted": "infra",
                "givenName": "infra",
                "familyName": ".",
            },
            "emails": [
                {
                    "value": "infra.teste@fmimpressos.com.br",
                    "type": "work",
                    "primary": True,
                }
            ],
            "active": True,
        }

        result = self.client.update_user_active(
            user_id="000240",
            active=False,
            current_payload=payload,
        )

        self.assertFalse(result["active"])
        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["json"]["id"], "000240")
        self.assertEqual(kwargs["json"]["userName"], "infra-teste")
        self.assertFalse(kwargs["json"]["active"])

    @mock.patch("integrations.totvs.client.requests.Session.request")
    def test_update_user_active_uses_fallback_email_when_primary_is_empty(self, request_mock):
        response = mock.Mock()
        response.json.return_value = {"id": "000180", "userName": "pedro.furtado", "active": False}
        response.raise_for_status.return_value = None
        request_mock.return_value = response

        payload = {
            "id": "000180",
            "userName": "pedro.furtado",
            "name": {
                "formatted": "Pedro Furtado",
                "givenName": "Pedro",
                "familyName": "Furtado",
            },
            "emails": [
                {
                    "value": "",
                    "type": "work",
                    "primary": True,
                }
            ],
            "active": True,
        }

        self.client.update_user_active(
            user_id="000180",
            active=False,
            current_payload=payload,
            fallback_email="pedro.furtado@printi.com.br",
        )

        _, kwargs = request_mock.call_args
        self.assertEqual(kwargs["json"]["emails"][0]["value"], "pedro.furtado@printi.com.br")


class TotvsIntegrationServiceTests(TestCase):
    def setUp(self):
        token = uuid.uuid4().hex[:8]
        self.login_ad = f"teste.totvs.{token}"
        self.colaborador = Colaborador.objects.create(
            nome="Teste TOTVS",
            email=f"teste.{token}@printi.com.br",
            login_ad=self.login_ad,
            ativo=True,
        )
        self.service = TotvsIntegrationService()

    @mock.patch("apps.totvs.services.TotvsIntegrationService.consultar_usuario")
    def test_sync_found_user_updates_db_with_real_status(self, consultar_mock):
        consultar_mock.return_value = mock.Mock(
            identifier=self.login_ad,
            user_id="000999",
            username=self.login_ad,
            active=False,
            status="BLOQUEADO",
            payload={"id": "000999", "active": False},
            found=True,
        )

        resolved = self.service.sincronizar_status_no_banco_por_login(login_ad=self.login_ad)

        self.assertTrue(resolved.found)
        acesso = Acesso.objects.get(colaborador_id=self.colaborador.id, sistema="TOTVS")
        self.assertEqual(acesso.status, "BLOQUEADO")

    @mock.patch("apps.totvs.services.TotvsIntegrationService.consultar_usuario")
    def test_sync_404_user_updates_db_to_np(self, consultar_mock):
        consultar_mock.side_effect = TotvsClientError(
            "Erro HTTP 404 ao chamar TOTVS: Id do usuário não encontrado",
            status_code=404,
            detail="Id do usuário não encontrado",
        )

        resolved = self.service.sincronizar_status_no_banco_por_login(login_ad=self.login_ad)

        self.assertFalse(resolved.found)
        self.assertEqual(resolved.status, "NP")
        acesso = Acesso.objects.get(colaborador_id=self.colaborador.id, sistema="TOTVS")
        self.assertEqual(acesso.status, "NP")
