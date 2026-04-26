from __future__ import annotations

from unittest.mock import patch

from django.test import TransactionTestCase

from apps.block.models import BlockProcessing, BlockVerificationItem, BlockVerificationRun
from apps.block.services import BlockService
from apps.people.models import Acesso

from .helpers import BlockIntegrationDataMixin


class BlockBusinessRulesTests(BlockIntegrationDataMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.service = BlockService()

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
        self.assertEqual(preview["rows"][0]["motivo"], "Saindo de férias hoje")

    def test_preview_mostra_usuario_em_ferias_e_nao_bloqueado_como_bloquear(self):
        self.preparar_cenario(
            scenario="ferias-atrasado",
            status_ad="LIBERADO",
            status_vpn="LIBERADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["bloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "BLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Em férias e ainda não bloqueado")

    def test_preview_mostra_usuario_retornando_hoje_como_desbloquear(self):
        self.preparar_cenario(
            scenario="retorno-hoje",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["desbloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "DESBLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Retornando de férias hoje")

    def test_preview_mostra_usuario_ja_retornado_e_bloqueado_como_desbloquear(self):
        self.preparar_cenario(
            scenario="retorno-atrasado",
            status_ad="BLOQUEADO",
            status_vpn="BLOQUEADA",
        )

        preview = self.service.previsualizar_verificacao_block()

        self.assertEqual(preview["summary"]["desbloquear"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "DESBLOQUEAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Já retornou e ainda está bloqueado")

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

    def test_preview_respeita_duplicidade_e_mostra_ignorar(self):
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

        self.assertEqual(preview["summary"]["ignorar"], 1)
        self.assertEqual(preview["rows"][0]["acao_prevista"], "IGNORAR")
        self.assertEqual(preview["rows"][0]["motivo"], "Já processado hoje com sucesso")

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
        self.assertIn("já estava liberado", item.motivo.lower())
        self.assertEqual(BlockProcessing.objects.count(), 0)

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
        self.assertEqual(resumo["total_ignorados"], 1)
        item = BlockVerificationItem.objects.get(colaborador_id=colaborador.id)
        self.assertEqual(item.acao_final, "IGNORAR")
        self.assertEqual(item.resultado_verificacao, BlockVerificationItem.OUTCOME_REMOVED)
        self.assertIn("já processado hoje", item.motivo.lower())

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

    def _assert_status(self, colaborador_id: int, sistema: str, esperado: str):
        acesso = Acesso.objects.get(colaborador_id=colaborador_id, sistema=sistema)
        self.assertEqual(acesso.status, esperado)

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
