from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.test import SimpleTestCase

from apps.bot.services import BotService, _format_schedule_datetime


class ScheduleFormattingTests(SimpleTestCase):
    def test_format_schedule_datetime_converts_utc_to_local_timezone(self) -> None:
        value = datetime(2026, 4, 29, 8, 0, tzinfo=dt_timezone.utc)

        formatted = _format_schedule_datetime(value)

        self.assertEqual(formatted, "29/04/2026 as 05:00")

    def test_format_schedule_datetime_handles_empty_values(self) -> None:
        self.assertEqual(_format_schedule_datetime(None), "-")


class BotTaskNotificationTests(SimpleTestCase):
    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.block.tasks.run_operational_verification")
    def test_operational_verification_from_bot_disables_task_notification(
        self,
        run_mock,
        reply_mock,
    ) -> None:
        run_mock.return_value = {"status": "success", "run_id": 1}

        BotService()._reply_verificacao_operacional("destino")

        run_mock.assert_called_once_with(notify=False)
        self.assertGreaterEqual(reply_mock.call_count, 2)

    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.sync.tasks.run_spreadsheet_sync")
    def test_spreadsheet_sync_from_bot_disables_task_notification(
        self,
        run_mock,
        reply_mock,
    ) -> None:
        run_mock.return_value = {"status": "success", "total": 10}

        BotService()._reply_sincronizar("destino")

        run_mock.assert_called_once_with(notify=False)
        self.assertGreaterEqual(reply_mock.call_count, 2)

    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.block.tasks.run_block_verification")
    def test_block_execution_from_bot_uses_operational_queue_and_disables_task_notification(
        self,
        run_mock,
        reply_mock,
    ) -> None:
        run_mock.return_value = {
            "bloqueios_feitos": 1,
            "desbloqueios_feitos": 0,
            "sincronizados": 0,
            "ignorados": 0,
            "erros": 0,
            "used_operational_queue": True,
        }

        BotService()._reply_executar_block("destino")

        run_mock.assert_called_once_with(
            notify=False,
            require_operational_queue=True,
        )
        self.assertGreaterEqual(reply_mock.call_count, 2)


class BotCommandParsingTests(SimpleTestCase):
    def test_parse_command_identifies_block_execution_aliases(self) -> None:
        service = BotService()

        self.assertEqual(service._parse_command("executar block"), "executar_block")
        self.assertEqual(service._parse_command("desblok"), "executar_block")

    def test_parse_command_identifies_totvs_lookup(self) -> None:
        service = BotService()

        self.assertEqual(service._parse_command("totvs gabriel"), "consultar_totvs")
        self.assertEqual(service._parse_command("totvs bloquear gabriel"), "bloquear_totvs")
        self.assertEqual(service._parse_command("totvs desbloquar gabriel"), "desbloquear_totvs")


class BotTotvsReplyTests(SimpleTestCase):
    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.bot.queries.BotQueryService.localizar_colaborador")
    @mock.patch("apps.totvs.services.TotvsIntegrationService")
    def test_reply_consultar_totvs_by_login(
        self,
        totvs_service_cls,
        localizar_mock,
        reply_mock,
    ) -> None:
        colaborador = mock.Mock(
            nome="Gabriel Vinicius Caetano",
            email="gabriel.caetano@printi.com.br",
            login_ad="gabriel.caetano",
        )
        localizar_mock.return_value = colaborador
        totvs_service = totvs_service_cls.return_value
        totvs_service.consultar_usuario.return_value = mock.Mock(active=False)

        BotService()._reply_consultar_totvs("destino", "gabriel")

        totvs_service.consultar_usuario.assert_called_once_with("gabriel.caetano")
        reply_mock.assert_called_once()
        mensagem = reply_mock.call_args.args[1]
        self.assertIn("Totvs - Gabriel Vinicius Caetano", mensagem)
        self.assertIn("Gabriel Vinicius Caetano", mensagem)
        self.assertIn("STATUS: BLOQUEADO", mensagem)

    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.bot.queries.BotQueryService.localizar_colaborador")
    @mock.patch("apps.totvs.services.TotvsIntegrationService")
    def test_reply_bloquear_totvs(
        self,
        totvs_service_cls,
        localizar_mock,
        reply_mock,
    ) -> None:
        colaborador = mock.Mock(
            nome="Gabriel Vinicius Caetano",
            email="gabriel.caetano@printi.com.br",
            login_ad="gabriel.caetano",
        )
        localizar_mock.return_value = colaborador
        totvs_service = totvs_service_cls.return_value
        totvs_service.atualizar_status_usuario.return_value = mock.Mock(active=False)

        BotService()._reply_alterar_totvs("destino", "gabriel", active=False)

        totvs_service.atualizar_status_usuario.assert_called_once_with(
            identifier="gabriel.caetano",
            active=False,
        )
        mensagem = reply_mock.call_args.args[1]
        self.assertIn("Totvs - Gabriel Vinicius Caetano", mensagem)
        self.assertIn("STATUS: BLOQUEADO", mensagem)

    @mock.patch("apps.bot.services.BotService._reply_text")
    @mock.patch("apps.bot.queries.BotQueryService.localizar_colaborador")
    @mock.patch("apps.totvs.services.TotvsIntegrationService")
    def test_reply_desbloquear_totvs(
        self,
        totvs_service_cls,
        localizar_mock,
        reply_mock,
    ) -> None:
        colaborador = mock.Mock(
            nome="Gabriel Vinicius Caetano",
            email="gabriel.caetano@printi.com.br",
            login_ad="gabriel.caetano",
        )
        localizar_mock.return_value = colaborador
        totvs_service = totvs_service_cls.return_value
        totvs_service.atualizar_status_usuario.return_value = mock.Mock(active=True)

        BotService()._reply_alterar_totvs("destino", "gabriel", active=True)

        totvs_service.atualizar_status_usuario.assert_called_once_with(
            identifier="gabriel.caetano",
            active=True,
        )
        mensagem = reply_mock.call_args.args[1]
        self.assertIn("Totvs - Gabriel Vinicius Caetano", mensagem)
        self.assertIn("STATUS: DESBLOQUEADO", mensagem)
