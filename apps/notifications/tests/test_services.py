from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from django.test import TestCase

from apps.notifications.models import (
    NotificationDelivery,
    NotificationDivergenceAudit,
    NotificationProviderConfig,
    NotificationTarget,
)
from apps.notifications.services import NotificationService


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.target = NotificationTarget.objects.create(
            name="Grupo Teste",
            target_type=NotificationTarget.TYPE_GROUP,
            destination="120363020985287866@g.us",
            enabled=True,
        )
        self.provider = NotificationProviderConfig.objects.create(
            name="Evolution",
            enabled=True,
            endpoint_url="http://localhost:8081/message/sendText/teste",
            api_key="token",
            default_target=self.target,
        )

    @patch("apps.notifications.providers.evolution.requests.post")
    def test_send_test_message_logs_delivery_as_sent(self, post_mock):
        response = Mock(status_code=201)
        response.json.return_value = {"key": "value"}
        post_mock.return_value = response

        delivery = NotificationService().send_test_message(
            provider_config=self.provider,
            text="Mensagem de teste",
        )

        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(NotificationDelivery.objects.count(), 1)
        post_mock.assert_called_once()

    def test_send_test_message_requires_enabled_provider(self):
        self.provider.enabled = False
        self.provider.save(update_fields=["enabled"])

        with self.assertRaisesMessage(ValueError, "desabilitado"):
            NotificationService().send_test_message(
                provider_config=self.provider,
                text="Mensagem de teste",
            )

    @patch("apps.notifications.providers.evolution.requests.post")
    def test_notify_task_status_falls_back_to_single_enabled_target_when_provider_has_no_default(self, post_mock):
        response = Mock(status_code=201)
        response.json.return_value = {"key": "value"}
        post_mock.return_value = response
        self.provider.default_target = None
        self.provider.save(update_fields=["default_target"])

        delivery = NotificationService().notify_task_status(
            task_key="spreadsheet_sync",
            task_label="Sincronizacao da planilha",
            status="success",
            summary="Sincronizados 2 eventos e 4 acessos.",
        )

        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.target_id, self.target.id)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        post_mock.assert_called_once()

    @patch("apps.notifications.providers.evolution.requests.post")
    def test_notify_operational_divergence_creates_audit_and_skips_duplicate(self, post_mock):
        response = Mock(status_code=201)
        response.json.return_value = {"key": "value"}
        post_mock.return_value = response

        service = NotificationService()
        audit, delivery = service.notify_operational_divergence(
            collaborator_id=10,
            collaborator_name="Gabriel Teste",
            usuario_ad="gabriel.teste",
            email="gabriel.teste@printi.com.br",
            system_name="AD PRIN",
            initial_action="DESBLOQUEAR",
            sheet_status="BLOQUEADO",
            real_status="LIBERADO",
            internal_status_after_sync="LIBERADO",
            vpn_sheet_status="LIBERADA",
            vpn_real_status="NP",
            vpn_internal_status_after_sync="NP",
            vpn_changed=True,
            data_saida=date(2026, 4, 1),
            data_retorno=date(2026, 4, 27),
            details={"origem": "teste"},
        )

        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertEqual(NotificationDivergenceAudit.objects.count(), 1)
        audit.refresh_from_db()
        self.assertIsNotNone(audit.notified_at)

        second_audit, second_delivery = service.notify_operational_divergence(
            collaborator_id=10,
            collaborator_name="Gabriel Teste",
            usuario_ad="gabriel.teste",
            email="gabriel.teste@printi.com.br",
            system_name="AD PRIN",
            initial_action="DESBLOQUEAR",
            sheet_status="BLOQUEADO",
            real_status="LIBERADO",
            internal_status_after_sync="LIBERADO",
            vpn_sheet_status="LIBERADA",
            vpn_real_status="NP",
            vpn_internal_status_after_sync="NP",
            vpn_changed=True,
            data_saida=date(2026, 4, 1),
            data_retorno=date(2026, 4, 27),
            details={"origem": "teste"},
        )

        self.assertEqual(second_audit.id, audit.id)
        self.assertEqual(second_delivery.status, NotificationDelivery.STATUS_SKIPPED)
        self.assertEqual(NotificationDivergenceAudit.objects.count(), 1)
        self.assertEqual(NotificationDelivery.objects.count(), 2)
        post_mock.assert_called_once()

    @patch("apps.notifications.providers.evolution.requests.post")
    def test_notify_task_status_sends_summary_message(self, post_mock):
        response = Mock(status_code=201)
        response.json.return_value = {"key": "value"}
        post_mock.return_value = response

        delivery = NotificationService().notify_task_status(
            task_key="spreadsheet_sync",
            task_label="Sincronizacao da planilha",
            status="success",
            summary="Sincronizados 2 eventos e 4 acessos.",
            details=["Pendencias: 0", "Arquivo: planilha.xlsx"],
        )

        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, NotificationDelivery.STATUS_SENT)
        self.assertIn("Sincronizacao da planilha", delivery.message_preview)
        post_mock.assert_called_once()
