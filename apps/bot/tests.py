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
