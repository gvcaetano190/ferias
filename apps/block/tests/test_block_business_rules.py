from __future__ import annotations

import tempfile
from unittest.mock import patch

from django.test import TransactionTestCase
from django.test.utils import override_settings

from apps.block.models import BlockProcessing, BlockVerificationItem, BlockVerificationRun
from apps.block.services import BlockService
from apps.notifications.models import (
    NotificationDelivery,
    NotificationDivergenceAudit,
    NotificationProviderConfig,
    NotificationTarget,
)
from apps.people.models import Acesso, Ferias
from apps.sync.services import SpreadsheetSyncService

from .helpers import BlockIntegrationDataMixin


class BlockBusinessRulesTests(BlockIntegrationDataMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.service = BlockService()
        self._totvs_consulta_patcher = patch.object(
            self.service.business_service.totvs_service,
            "consultar_usuarios_operacionais",
            side_effect=self._fake_consultar_usuarios_totvs,
        )
        self._totvs_bloqueio_patcher = patch.object(
            self.service.business_service.totvs_service,
            "bloquear_usuarios_operacionais",
            side_effect=self._fake_bloquear_usuarios_totvs,
        )
        self._totvs_desbloqueio_patcher = patch.object(
            self.service.business_service.totvs_service,
            "desbloquear_usuarios_operacionais",
            side_effect=self._fake_desbloquear_usuarios_totvs,
        )
        self._totvs_consulta_patcher.start()
        self._totvs_bloqueio_patcher.start()
        self._totvs_desbloqueio_patcher.start()
        self.addCleanup(self._totvs_consulta_patcher.stop)
        self.addCleanup(self._totvs_bloqueio_patcher.stop)
        self.addCleanup(self._totvs_desbloqueio_patcher.stop)
        self.notification_target = NotificationTarget.objects.create(
            name="Grupo Operacional",
            target_type=NotificationTarget.TYPE_GROUP,
            destination="120363020985287866@g.us",
            enabled=True,
        )
        self.notification_provider = NotificationProviderConfig.objects.create(
            name="Evolution Teste",
            enabled=True,
            endpoint_url="http://localhost:8081/message/sendText/teste",
            api_key="token",
            default_target=self.notification_target,
        )

    def _fake_consultar_usuarios_totvs(self, identifiers):
        resultados = []
        for identifier in identifiers:
            colaborador = self._resolver_colaborador_por_login(identifier)
            status = self._status_totvs_colaborador(colaborador)
            resultados.append(
                {
                    "success": True,
                    "usuario_ad": identifier,
                    "totvs_user_id": f"totvs-{identifier}",
                    "totvs_status": status,
                    "message": "Consulta TOTVS simulada com sucesso.",
                    "user_found": status != "NP",
                    "active": status == "LIBERADO",
                }
            )
        return resultados

    def _fake_bloquear_usuarios_totvs(self, identifiers):
        return [
            {
                "success": True,
                "usuario_ad": identifier,
                "totvs_user_id": f"totvs-{identifier}",
                "totvs_status": "BLOQUEADO",
                "message": "Bloqueio TOTVS simulado com sucesso.",
                "user_found": True,
                "active": False,
            }
            for identifier in identifiers
        ]

    def _fake_desbloquear_usuarios_totvs(self, identifiers):
        return [
            {
                "success": True,
                "usuario_ad": identifier,
                "totvs_user_id": f"totvs-{identifier}",
                "totvs_status": "LIBERADO",
                "message": "Desbloqueio TOTVS simulado com sucesso.",
                "user_found": True,
                "active": True,
            }
            for identifier in identifiers
        ]

    def _resolver_colaborador_por_login(self, identifier):
        return self.service.business_service.repository.obter_colaborador_por_login_ou_email(
            usuario_ad=identifier,
            email="",
        )

    def _status_totvs_colaborador(self, colaborador):
        if not colaborador:
            return "NP"
        acesso = Acesso.objects.filter(
            colaborador_id=colaborador.id,
            sistema=self.totvs_system_name,
        ).order_by("-updated_at", "-id").first()
        return (getattr(acesso, "status", "") or "NP").strip().upper()

    def test_saida_hoje_bloqueia_e_bloqueia_vpn_quando_usuario_esta_no_grupo(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        consultar_payload = self._consulta_liberado(vpn_status="LIBERADA", is_in_printi_acesso=True)
        bloquear_payload = self._bloqueio_sucesso(vpn_status="BLOQUEADA", is_in_printi_acesso=True)

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[consultar_payload]) as consultar_mock:
            with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[bloquear_payload]) as bloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["bloqueios_feitos"], 1)
        self.assertEqual(resultado["desbloqueios_feitos"], 0)
        self.assertEqual(resultado["sincronizados"], 0)
        self.assertEqual(resultado["erros"], 0)
        self.assertEqual(resultado["ignorados"], 0)
        bloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
        self._assert_status(colaborador.id, self.vpn_system_name, "BLOQUEADA")
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            ad_status="BLOQUEADO",
            vpn_status="BLOQUEADA",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
        )

    def test_saida_hoje_bloqueia_e_mantem_vpn_np_quando_usuario_nao_tem_grupo(self):
        colaborador, _ = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="NP",
        )
        consultar_payload = self._consulta_liberado(vpn_status="NP", is_in_printi_acesso=False)
        bloquear_payload = self._bloqueio_sucesso(vpn_status="NP", is_in_printi_acesso=False)

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[consultar_payload]):
            with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[bloquear_payload]) as bloquear_mock:
                self.service.processar_verificacao_block()

        bloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            ad_status="BLOQUEADO",
            vpn_status="NP",
        )

    def test_retorno_hoje_desbloqueia_e_atualiza_log(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )
        consultar_payload = self._consulta_bloqueado(vpn_status="BLOQUEADA")
        desbloquear_payload = self._desbloqueio_sucesso()

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[consultar_payload]):
            with patch("apps.block.business_service.desbloquear_usuarios_ad", return_value=[desbloquear_payload]) as desbloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["desbloqueios_feitos"], 1)
        desbloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_status(colaborador.id, self.ad_system_name, "LIBERADO")
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="DESBLOQUEIO",
            resultado="SUCESSO",
            ad_status="LIBERADO",
            vpn_status="NP",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
        )

    def test_ferias_atrasado_bloqueia_quando_nao_rodou_no_dia_da_saida(self):
        colaborador, _ = self.preparar_cenario(
            scenario="ferias-atrasado",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]):
            with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[self._bloqueio_sucesso()]) as bloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["bloqueios_feitos"], 1)
        bloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            ad_status="BLOQUEADO",
        )

    def test_retorno_atrasado_desbloqueia_quando_nao_rodou_no_dia_do_retorno(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=self._consulta_bloqueado(vpn_status="BLOQUEADA")):
            with patch("apps.block.business_service.desbloquear_usuarios_ad", return_value=[self._desbloqueio_sucesso()]) as desbloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["desbloqueios_feitos"], 1)
        desbloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_status(colaborador.id, self.ad_system_name, "LIBERADO")
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="DESBLOQUEIO",
            resultado="SUCESSO",
            ad_status="LIBERADO",
        )

    def test_nao_executa_bloqueio_duplicado_quando_ja_existe_sucesso_hoje(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        self.criar_processamento(
            colaborador=colaborador,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status="BLOQUEADO",
            vpn_status="BLOQUEADA",
            mensagem="Bloqueio anterior",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]):
            with patch("apps.block.business_service.bloquear_usuarios_ad") as bloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["ignorados"], 1)
        bloquear_mock.assert_not_called()
        self.assertEqual(BlockProcessing.objects.filter(colaborador_id=colaborador.id, acao="BLOQUEIO").count(), 2)
        self.assertTrue(
            BlockProcessing.objects.filter(
                colaborador_id=colaborador.id,
                acao="BLOQUEIO",
                resultado="IGNORADO",
            ).exists()
        )

    def test_nao_executa_desbloqueio_duplicado_quando_ja_existe_sucesso_hoje(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )
        self.criar_processamento(
            colaborador=colaborador,
            acao="DESBLOQUEIO",
            resultado="SUCESSO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status="LIBERADO",
            vpn_status="NP",
            mensagem="Desbloqueio anterior",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=self._consulta_bloqueado(vpn_status="BLOQUEADA")):
            with patch("apps.block.business_service.desbloquear_usuarios_ad") as desbloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["ignorados"], 1)
        desbloquear_mock.assert_not_called()
        self.assertEqual(BlockProcessing.objects.filter(colaborador_id=colaborador.id, acao="DESBLOQUEIO").count(), 2)
        self.assertTrue(
            BlockProcessing.objects.filter(
                colaborador_id=colaborador.id,
                acao="DESBLOQUEIO",
                resultado="IGNORADO",
            ).exists()
        )

    def test_tenta_novamente_quando_houve_erro_anterior_no_mesmo_dia(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        self.criar_processamento(
            colaborador=colaborador,
            acao="BLOQUEIO",
            resultado="ERRO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status="ERRO",
            vpn_status="NP",
            mensagem="Falha anterior",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]):
            with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[self._bloqueio_sucesso()]) as bloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertEqual(resultado["bloqueios_feitos"], 1)
        bloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self.assertEqual(BlockProcessing.objects.filter(colaborador_id=colaborador.id, acao="BLOQUEIO").count(), 2)
        self.assertEqual(
            BlockProcessing.objects.filter(
                colaborador_id=colaborador.id,
                acao="BLOQUEIO",
                resultado="SUCESSO",
            ).count(),
            1,
        )

    def test_preview_mostra_execucao_planejada_sem_chamar_executor_de_escrita(self):
        self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad") as consultar_mock:
            with patch("apps.block.business_service.bloquear_usuarios_ad") as bloquear_mock:
                preview = self.service.previsualizar_verificacao_block()

        consultar_mock.assert_not_called()
        bloquear_mock.assert_not_called()
        self.assertEqual(preview["summary"]["total"], 1)
        self.assertEqual(preview["summary"]["bloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "BLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Saindo de ferias hoje")

    def test_preview_mostra_usuario_em_ferias_e_nao_bloqueado_como_bloquear(self):
        self.preparar_cenario(
            scenario="ferias-atrasado",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["bloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "BLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Em ferias e ainda nao bloqueado")

    def test_preview_mostra_usuario_retornando_hoje_como_desbloquear(self):
        self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["desbloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "DESBLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Retornando de ferias hoje")

    def test_preview_mostra_usuario_ja_retornado_e_bloqueado_como_desbloquear(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["desbloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "DESBLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Ja retornou e ainda esta bloqueado")

    def test_preview_nao_altera_banco_nem_grava_processamento(self):
        colaborador, _ = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        ad_antes = Acesso.objects.get(colaborador_id=colaborador.id, sistema=self.ad_system_name).status
        vpn_antes = Acesso.objects.get(colaborador_id=colaborador.id, sistema=self.vpn_system_name).status
        processamentos_antes = BlockProcessing.objects.count()

        self.service.previsualizar_verificacao_block()

        self.assertEqual(Acesso.objects.get(colaborador_id=colaborador.id, sistema=self.ad_system_name).status, ad_antes)
        self.assertEqual(Acesso.objects.get(colaborador_id=colaborador.id, sistema=self.vpn_system_name).status, vpn_antes)
        self.assertEqual(BlockProcessing.objects.count(), processamentos_antes)

    def test_preview_remove_da_lista_quem_ja_foi_processado_hoje(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        self.criar_processamento(
            colaborador=colaborador,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status="BLOQUEADO",
            vpn_status="BLOQUEADA",
            mensagem="Bloqueio anterior",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["ignorar"], 0)
        self.assertEqual(preview["summary"]["total"], 0)
        self.assertEqual(preview["rows"], [])

    def test_preview_nao_chama_nenhum_executor_ad(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad") as consultar_mock:
            with patch("apps.block.business_service.bloquear_usuarios_ad") as bloquear_mock:
                with patch("apps.block.business_service.desbloquear_usuarios_ad") as desbloquear_mock:
                    self.service.previsualizar_verificacao_block()

        consultar_mock.assert_not_called()
        bloquear_mock.assert_not_called()
        desbloquear_mock.assert_not_called()

    def test_verificacao_operacional_mantem_usuario_na_fila_final_de_bloqueio(self):
        colaborador, _ = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]) as consultar_lote_mock:
            resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_inicial_bloqueio"], 1)
        self.assertEqual(resumo["total_final_bloqueio"], 1)
        self.assertEqual(resumo["total_sincronizados"], 0)
        consultar_lote_mock.assert_called_once()
        self.assertEqual(BlockVerificationRun.objects.count(), 1)
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_inicial, "BLOQUEAR")
        self.assertEqual(item.acao_final, "BLOQUEAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_KEPT)
        self.assertEqual(BlockProcessing.objects.count(), 0)

    def test_verificacao_operacional_reduz_lista_e_sincroniza_quando_ad_ja_esta_correto(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="NP")]) as consultar_lote_mock:
            with patch("apps.notifications.providers.evolution.requests.post") as post_mock:
                mock_response = post_mock.return_value
                mock_response.status_code = 201
                mock_response.json.return_value = {"key": "value"}
                resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_inicial_desbloqueio"], 1)
        self.assertEqual(resumo["total_final_desbloqueio"], 0)
        self.assertEqual(resumo["total_sincronizados"], 1)
        consultar_lote_mock.assert_called_once()
        self._assert_status(colaborador.id, self.ad_system_name, "LIBERADO")
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_inicial, "DESBLOQUEAR")
        self.assertEqual(item.acao_final, "IGNORAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_SYNCED)
        self.assertIn("ja estava liberado", item.motivo.lower())
        self.assertEqual(BlockProcessing.objects.count(), 0)
        self.assertEqual(NotificationDivergenceAudit.objects.count(), 1)
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.divergence.validated",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.task.status",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        self.assertEqual(post_mock.call_count, 2)

    def test_verificacao_operacional_nao_reenvia_notificacao_para_mesma_divergencia(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="NP")]):
            with patch("apps.notifications.providers.evolution.requests.post") as post_mock:
                mock_response = post_mock.return_value
                mock_response.status_code = 201
                mock_response.json.return_value = {"key": "value"}
                self.service.processar_verificacao_operacional_block()
                self.service.processar_verificacao_operacional_block()

        self.assertEqual(NotificationDivergenceAudit.objects.count(), 1)
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.divergence.validated",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.task.status",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            2,
        )
        self.assertEqual(post_mock.call_count, 3)

    def test_verificacao_operacional_envia_notificacao_de_status_ao_final(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch.object(self.service.business_service.notification_service, "notify_task_status") as notify_mock:
            with patch.object(self.service.business_service.notification_service, "notify_operational_divergence") as divergence_mock:
                with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="NP")]):
                    self.service.processar_verificacao_operacional_block()

        notify_mock.assert_called_once()
        divergence_mock.assert_called_once()
        self.assertEqual(notify_mock.call_args.kwargs["task_key"], "block_operational_check")

    def test_execucao_final_envia_notificacao_de_status_ao_final(self):
        self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        with patch.object(self.service.business_service.notification_service, "notify_task_status") as notify_mock:
            with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]):
                with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[self._bloqueio_sucesso()]):
                    self.service.processar_verificacao_block()

        notify_mock.assert_called_once()
        self.assertEqual(notify_mock.call_args.kwargs["task_key"], "block_execution")

    def test_verificacao_operacional_sincroniza_vpn_para_np_quando_usuario_nao_esta_no_grupo(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="LIBERADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA", is_in_printi_acesso=False)]):
            with patch("apps.notifications.providers.evolution.requests.post") as post_mock:
                mock_response = post_mock.return_value
                mock_response.status_code = 201
                mock_response.json.return_value = {"key": "value"}
                resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_sincronizados"], 1)
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.divergence.validated",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        post_mock.assert_called()

    def test_verificacao_operacional_sincroniza_vpn_para_liberada_quando_usuario_esta_no_grupo(self):
        colaborador, _ = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="NP",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="NP", is_in_printi_acesso=True)]):
            with patch("apps.notifications.providers.evolution.requests.post") as post_mock:
                mock_response = post_mock.return_value
                mock_response.status_code = 201
                mock_response.json.return_value = {"key": "value"}
                resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_final_bloqueio"], 1)
        self._assert_status(colaborador.id, self.vpn_system_name, "LIBERADA")
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_final, "BLOQUEAR")
        self.assertEqual(item.vpn_status_banco_depois, "LIBERADA")
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.divergence.validated",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        post_mock.assert_called()

    def test_verificacao_operacional_inclui_np_np_em_desbloqueio_e_sincroniza_quando_usuario_existe(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="NP",
            status_vpn="NP",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_bloqueado(vpn_status="NP", is_in_printi_acesso=False)]):
            with patch("apps.notifications.providers.evolution.requests.post") as post_mock:
                mock_response = post_mock.return_value
                mock_response.status_code = 201
                mock_response.json.return_value = {"key": "value"}
                resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_inicial_desbloqueio"], 1)
        self.assertEqual(resumo["total_final_desbloqueio"], 1)
        self.assertEqual(resumo["total_sincronizados"], 0)
        self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_inicial, "DESBLOQUEAR")
        self.assertEqual(item.acao_final, "DESBLOQUEAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_KEPT)
        self.assertEqual(item.ad_status_banco_antes, "NP")
        self.assertEqual(item.ad_status_banco_depois, "BLOQUEADO")
        self.assertEqual(
            NotificationDelivery.objects.filter(
                event_key="notifications.divergence.validated",
                status=NotificationDelivery.STATUS_SENT,
            ).count(),
            1,
        )
        post_mock.assert_called()

    def test_verificacao_operacional_inclui_np_np_e_mantem_np_quando_usuario_nao_existe_no_ad(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="NP",
            status_vpn="NP",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_nao_encontrado()]):
            resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_inicial_desbloqueio"], 1)
        self.assertEqual(resumo["total_final_desbloqueio"], 0)
        self.assertEqual(resumo["total_ignorados"], 1)
        self._assert_status(colaborador.id, self.ad_system_name, "NP")
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_final, "IGNORAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_REMOVED)
        self.assertIn("status np mantido", item.motivo.lower())

    def test_verificacao_operacional_exibe_mensagem_amigavel_quando_ad_nao_localiza_objeto(self):
        colaborador, _ = self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="NP",
            status_vpn="NP",
        )

        consulta = {
            "success": False,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": False,
            "ad_status": "ERRO",
            "vpn_status": "NP",
            "message": (
                f"NÃ£o Ã© possÃ­vel localizar um objeto com identidade: "
                f"'{self.usuario_ad_teste}' em: 'DC=printi,DC=local'."
            ),
            "is_enabled": False,
            "is_in_printi_acesso": False,
            "already_in_desired_state": False,
        }

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[consulta]):
            resumo = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo["total_erros"], 1)
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_final, "IGNORAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_ERROR)
        self.assertIn("usuario nao encontrado no ad", item.motivo.lower())
        self.assertIn(self.usuario_ad_teste, item.motivo)

    def test_verificacao_operacional_registra_motivo_quando_ja_processado_hoje(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )
        self.criar_processamento(
            colaborador=colaborador,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
            ad_status="BLOQUEADO",
            vpn_status="BLOQUEADA",
            mensagem="Bloqueio anterior",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad") as consultar_mock:
            resumo = self.service.processar_verificacao_operacional_block()

        consultar_mock.assert_not_called()
        self.assertEqual(resumo["total_ignorados"], 0)
        self.assertFalse(BlockVerificationItem.objects.filter(colaborador_id=colaborador.id).exists())

    def test_execucao_final_usa_fila_final_da_verificacao_operacional(self):
        colaborador, ferias = self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]):
            resumo_verificacao = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo_verificacao["total_final_bloqueio"], 1)

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="LIBERADA")]) as consultar_mock:
            with patch("apps.block.business_service.bloquear_usuarios_ad", return_value=[self._bloqueio_sucesso()]) as bloquear_mock:
                resultado = self.service.processar_verificacao_block() # changed

        self.assertTrue(resultado["used_operational_queue"])
        self.assertEqual(resultado["verification_run_id"], BlockVerificationRun.objects.first().id)
        bloquear_mock.assert_called_once_with([self.usuario_ad_teste])
        self._assert_processing(
            colaborador_id=colaborador.id,
            acao="BLOQUEIO",
            resultado="SUCESSO",
            ad_status="BLOQUEADO",
            vpn_status="BLOQUEADA",
            data_saida=ferias.data_saida,
            data_retorno=ferias.data_retorno,
        )

    def test_modal_da_verificacao_operacional_separa_lista_inicial_e_fila_final(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        with patch("apps.block.business_service.consultar_usuarios_ad", return_value=[self._consulta_liberado(vpn_status="NP")]):
            resumo_verificacao = self.service.processar_verificacao_operacional_block()

        self.assertEqual(resumo_verificacao["total_final_desbloqueio"], 0)
        modal = self.service.ver_detalhes_verificacao_operacional()

        self.assertIsNotNone(modal["run"])
        self.assertEqual(len(modal["lista_inicial"]), 1)
        self.assertEqual(len(modal["lista_final"]), 0)
        self.assertEqual(len(modal["lista_sincronizada"]), 1)
        self.assertTrue(modal["queue_is_source_for_next_job"])

    def test_execucao_pode_ser_bloqueada_quando_scheduler_exige_fila_operacional(self):
        self.preparar_cenario(
            scenario="saida-hoje",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        resultado = self.service.processar_verificacao_block(require_operational_queue=True)

        self.assertTrue(resultado["skipped"])
        self.assertFalse(resultado["used_operational_queue"])
        self.assertIn("aguardando", resultado["message"].lower())

    def test_sync_repetida_nao_recria_prelista_quando_check_operacional_ja_sincronizou_status_real(self):
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates("saida-hoje")
        records = [
            {
                "nome": colaborador.nome,
                "email": colaborador.email,
                "login_ad": colaborador.login_ad,
                "unidade": "Operacoes",
                "motivo": "Ferias",
                "data_saida": datas.data_saida.strftime("%Y-%m-%d"),
                "data_retorno": datas.data_retorno.strftime("%Y-%m-%d"),
                "gestor": "Gestor Teste",
                "aba_origem": "Abril 2026",
                "mes": datas.data_retorno.month,
                "ano": datas.data_retorno.year,
                "acessos": {
                    "AD PRIN": "NB",
                    "VPN": "NP",
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(
                DOWNLOAD_DIR=self._tmp_path(temp_dir, "downloads"),
                PENDING_SYNC_CSV=self._tmp_path(temp_dir, "pendencias_sync_ferias.csv"),
            ):
                service = SpreadsheetSyncService()

                self._executar_sync_fake(service, records)
                preview_inicial = self.service.previsualizar_verificacao_block()
                self.assertEqual(preview_inicial["summary"]["bloquear"], 1)
                self._assert_status(colaborador.id, self.ad_system_name, "NB")

                with patch(
                    "apps.block.business_service.consultar_usuarios_ad",
                    return_value=[self._consulta_bloqueado(vpn_status="BLOQUEADA")],
                ):
                    resumo_verificacao = self.service.processar_verificacao_operacional_block()

                self.assertEqual(resumo_verificacao["total_sincronizados"], 1)
                self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")

                self._executar_sync_fake(service, records)
                self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")

                preview_final = self.service.previsualizar_verificacao_block()
                self.assertEqual(preview_final["summary"]["total"], 0)

    def test_sync_np_na_planilha_preserva_status_operacional_ja_confirmado(self):
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates("saida-hoje")
        records_iniciais = [
            {
                "nome": colaborador.nome,
                "email": colaborador.email,
                "login_ad": colaborador.login_ad,
                "unidade": "Operacoes",
                "motivo": "Ferias",
                "data_saida": datas.data_saida.strftime("%Y-%m-%d"),
                "data_retorno": datas.data_retorno.strftime("%Y-%m-%d"),
                "gestor": "Gestor Teste",
                "aba_origem": "Abril 2026",
                "mes": datas.data_retorno.month,
                "ano": datas.data_retorno.year,
                "acessos": {
                    "AD PRIN": "NB",
                    "VPN": "NP",
                },
            }
        ]
        records_com_np = [
            {
                **records_iniciais[0],
                "acessos": {
                    "AD PRIN": "NP",
                    "VPN": "NP",
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(
                DOWNLOAD_DIR=self._tmp_path(temp_dir, "downloads"),
                PENDING_SYNC_CSV=self._tmp_path(temp_dir, "pendencias_sync_ferias.csv"),
            ):
                service = SpreadsheetSyncService()

                self._executar_sync_fake(service, records_iniciais)
                with patch(
                    "apps.block.business_service.consultar_usuarios_ad",
                    return_value=[self._consulta_bloqueado(vpn_status="BLOQUEADA")],
                ):
                    resumo_verificacao = self.service.processar_verificacao_operacional_block()

                self.assertEqual(resumo_verificacao["total_sincronizados"], 1)
                self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
                self._assert_status(colaborador.id, self.vpn_system_name, "LIBERADA")

                self._executar_sync_fake(service, records_com_np)
                self._assert_status(colaborador.id, self.ad_system_name, "BLOQUEADO")
                self._assert_status(colaborador.id, self.vpn_system_name, "LIBERADA")

                preview_final = self.service.previsualizar_verificacao_block()
                self.assertEqual(preview_final["summary"]["total"], 0)

    def test_sync_np_na_planilha_mantem_np_sem_historico_operacional_confiavel(self):
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates("saida-hoje")
        records = [
            {
                "nome": colaborador.nome,
                "email": colaborador.email,
                "login_ad": colaborador.login_ad,
                "unidade": "Operacoes",
                "motivo": "Ferias",
                "data_saida": datas.data_saida.strftime("%Y-%m-%d"),
                "data_retorno": datas.data_retorno.strftime("%Y-%m-%d"),
                "gestor": "Gestor Teste",
                "aba_origem": "Abril 2026",
                "mes": datas.data_retorno.month,
                "ano": datas.data_retorno.year,
                "acessos": {
                    "AD PRIN": "NP",
                    "VPN": "NP",
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(
                DOWNLOAD_DIR=self._tmp_path(temp_dir, "downloads"),
                PENDING_SYNC_CSV=self._tmp_path(temp_dir, "pendencias_sync_ferias.csv"),
            ):
                service = SpreadsheetSyncService()
                self._executar_sync_fake(service, records)

        self._assert_status(colaborador.id, self.ad_system_name, "NP")
        self._assert_status(colaborador.id, self.vpn_system_name, "NP")

    def test_sync_envia_notificacao_de_status_ao_final(self):
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates("saida-hoje")
        records = [
            {
                "nome": colaborador.nome,
                "email": colaborador.email,
                "login_ad": colaborador.login_ad,
                "unidade": "Operacoes",
                "motivo": "Ferias",
                "data_saida": datas.data_saida.strftime("%Y-%m-%d"),
                "data_retorno": datas.data_retorno.strftime("%Y-%m-%d"),
                "gestor": "Gestor Teste",
                "aba_origem": "Abril 2026",
                "mes": datas.data_retorno.month,
                "ano": datas.data_retorno.year,
                "acessos": {
                    "AD PRIN": "NB",
                    "VPN": "NP",
                },
            }
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(
                DOWNLOAD_DIR=self._tmp_path(temp_dir, "downloads"),
                PENDING_SYNC_CSV=self._tmp_path(temp_dir, "pendencias_sync_ferias.csv"),
            ):
                service = SpreadsheetSyncService()
                with patch.object(service.notification_service, "notify_task_status") as notify_mock:
                    self._executar_sync_fake(service, records)

        notify_mock.assert_called_once()
        self.assertEqual(notify_mock.call_args.kwargs["task_key"], "spreadsheet_sync")

    def test_reconcile_operational_sync_data_suporta_muitos_registros_sem_estourar_expressao(self):
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates("saida-hoje")
        service = SpreadsheetSyncService()

        ferias = self.criar_ferias(
            colaborador,
            data_saida=datas.data_saida,
            data_retorno=datas.data_retorno,
        )
        seen_ferias_keys = {
            (
                colaborador.id,
                datas.data_saida.isoformat(),
                datas.data_retorno.isoformat(),
                datas.data_retorno.month,
                datas.data_retorno.year,
            )
        }

        seen_access_keys = set()
        for index in range(1105):
            sistema = f"SISTEMA_{index}"
            self.criar_acesso(colaborador, sistema=sistema, status="LIBERADO")
            if index < 5:
                seen_access_keys.add((colaborador.id, sistema))

        service.reconcile_operational_sync_data(
            seen_ferias_keys=seen_ferias_keys,
            seen_access_keys=seen_access_keys,
        )

        self.assertTrue(Ferias.objects.filter(id=ferias.id).exists())
        self.assertEqual(Acesso.objects.filter(colaborador_id=colaborador.id).count(), 5)

    def _assert_status(self, colaborador_id: int, sistema: str, esperado: str):
        acesso = Acesso.objects.get(colaborador_id=colaborador_id, sistema=sistema)
        self.assertEqual(acesso.status, esperado)

    def _executar_sync_fake(self, service: SpreadsheetSyncService, records: list[dict]):
        with patch.object(service, "download_spreadsheet", return_value=self._tmp_path("." , "planilha_fake.xlsx")):
            with patch.object(service, "calculate_hash", return_value="hash-simulada"):
                with patch.object(service, "last_hash", return_value="hash-anterior"):
                    with patch.object(service, "process_workbook", return_value=(records, [{"nome": "Abril 2026"}])):
                        return service.run(force=True)

    def _tmp_path(self, *parts: str):
        from pathlib import Path

        return Path(parts[0]).joinpath(*parts[1:])

    def _assert_processing(
        self,
        *,
        colaborador_id: int,
        acao: str,
        resultado: str,
        ad_status: str,
        vpn_status: str | None = None,
        data_saida=None,
        data_retorno=None,
    ):
        processing = BlockProcessing.objects.filter(colaborador_id=colaborador_id, acao=acao).latest("executado_em")
        self.assertEqual(processing.resultado, resultado)
        self.assertEqual(processing.ad_status, ad_status)
        if vpn_status is not None:
            self.assertEqual(processing.vpn_status, vpn_status)
        if data_saida is not None:
            self.assertEqual(processing.data_saida, data_saida)
        if data_retorno is not None:
            self.assertEqual(processing.data_retorno, data_retorno)

    def _consulta_liberado(self, *, vpn_status="LIBERADA", is_in_printi_acesso=True):
        return {
            "success": True,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": True,
            "ad_status": "LIBERADO",
            "vpn_status": vpn_status,
            "message": "Consulta AD realizada com sucesso",
            "is_enabled": True,
            "is_in_printi_acesso": is_in_printi_acesso,
            "already_in_desired_state": False,
        }

    def _consulta_bloqueado(self, *, vpn_status="BLOQUEADA", is_in_printi_acesso=True):
        return {
            "success": True,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": True,
            "ad_status": "BLOQUEADO",
            "vpn_status": vpn_status,
            "message": "Consulta AD realizada com sucesso",
            "is_enabled": False,
            "is_in_printi_acesso": is_in_printi_acesso,
            "already_in_desired_state": False,
        }

    def _bloqueio_sucesso(self, *, vpn_status="BLOQUEADA", is_in_printi_acesso=True):
        return {
            "success": True,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": True,
            "is_in_printi_acesso": is_in_printi_acesso,
            "ad_status": "BLOQUEADO",
            "vpn_status": vpn_status,
            "message": "Usuario bloqueado com sucesso",
            "already_in_desired_state": False,
        }

    def _desbloqueio_sucesso(self):
        return {
            "success": True,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": True,
            "is_in_printi_acesso": False,
            "ad_status": "LIBERADO",
            "vpn_status": "NP",
            "message": "Usuario desbloqueado com sucesso",
            "already_in_desired_state": False,
        }

    def _consulta_nao_encontrado(self):
        return {
            "success": False,
            "usuario_ad": self.usuario_ad_teste,
            "user_found": False,
            "ad_status": "ERRO",
            "vpn_status": "NP",
            "message": "Usuario nao encontrado no AD",
            "is_enabled": False,
            "is_in_printi_acesso": False,
            "already_in_desired_state": False,
        }


