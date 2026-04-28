from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from apps.block.tasks import run_block_verification


class BlockTasksTests(SimpleTestCase):
    @mock.patch("apps.block.tasks.BlockBusinessService")
    def test_run_block_verification_forwards_operational_queue_flag(self, service_cls) -> None:
        service = service_cls.return_value
        service.processar_verificacao_block.return_value = {"status": "success"}

        result = run_block_verification(
            notify=False,
            require_operational_queue=True,
        )

        self.assertEqual(result, {"status": "success"})
        service.processar_verificacao_block.assert_called_once_with(
            notify=False,
            require_operational_queue=True,
        )
