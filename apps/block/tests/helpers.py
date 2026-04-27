from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from apps.block.models import BlockConfig, BlockProcessing, BlockVerificationItem, BlockVerificationRun
from apps.people.models import Acesso, Colaborador, Ferias, SyncLog


@dataclass(frozen=True)
class ScenarioDates:
    data_saida: object
    data_retorno: object


class BlockIntegrationDataMixin:
    usuario_ad_teste = "teste-infra"
    nome_teste = "Usuario Teste Infra"
    email_teste = "teste-infra@teste.local"
    ad_system_name = "AD PRIN"
    vpn_system_name = "VPN"
    _legacy_models = (Colaborador, Ferias, Acesso, SyncLog)
    _created_tables: list[str] = []

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._ensure_legacy_tables()

    @classmethod
    def tearDownClass(cls):
        try:
            cls._drop_legacy_tables()
        finally:
            super().tearDownClass()

    @classmethod
    def _ensure_legacy_tables(cls):
        existing_tables = set(connection.introspection.table_names())
        cls._created_tables = []
        with connection.schema_editor() as schema_editor:
            for model in cls._legacy_models:
                if model._meta.db_table in existing_tables:
                    continue
                schema_editor.create_model(model)
                cls._created_tables.append(model._meta.db_table)
                existing_tables.add(model._meta.db_table)

    @classmethod
    def _drop_legacy_tables(cls):
        if not cls._created_tables:
            return
        existing_tables = set(connection.introspection.table_names())
        with connection.schema_editor() as schema_editor:
            for model in reversed(cls._legacy_models):
                table_name = model._meta.db_table
                if table_name not in cls._created_tables or table_name not in existing_tables:
                    continue
                schema_editor.delete_model(model)
                existing_tables.remove(table_name)
        cls._created_tables = []

    def setUp(self):
        super().setUp()
        self._clean_block_data()

    def _clean_block_data(self):
        BlockVerificationItem.objects.all().delete()
        BlockVerificationRun.objects.all().delete()
        BlockProcessing.objects.all().delete()
        BlockConfig.objects.all().delete()
        SyncLog.objects.all().delete()
        Acesso.objects.all().delete()
        Ferias.objects.all().delete()
        Colaborador.objects.all().delete()

    def today(self):
        return timezone.localdate()

    def scenario_dates(self, scenario: str) -> ScenarioDates:
        today = self.today()
        if scenario == "saida-hoje":
            return ScenarioDates(data_saida=today, data_retorno=today + timedelta(days=5))
        if scenario == "retorno-hoje":
            return ScenarioDates(data_saida=today - timedelta(days=5), data_retorno=today)
        if scenario == "ferias-atrasado":
            return ScenarioDates(data_saida=today - timedelta(days=2), data_retorno=today + timedelta(days=3))
        if scenario == "retorno-atrasado":
            return ScenarioDates(data_saida=today - timedelta(days=8), data_retorno=today - timedelta(days=1))
        raise ValueError(f"Cenario desconhecido: {scenario}")

    def criar_colaborador_teste(self) -> Colaborador:
        return Colaborador.objects.create(
            nome=self.nome_teste,
            email=self.email_teste,
            login_ad=self.usuario_ad_teste,
            ativo=True,
        )

    def criar_ferias(self, colaborador: Colaborador, *, data_saida, data_retorno) -> Ferias:
        return Ferias.objects.create(
            colaborador=colaborador,
            data_saida=data_saida,
            data_retorno=data_retorno,
            mes_ref=data_retorno.month,
            ano_ref=data_retorno.year,
        )

    def criar_acesso(self, colaborador: Colaborador, *, sistema: str, status: str) -> Acesso:
        return Acesso.objects.create(
            colaborador=colaborador,
            sistema=sistema,
            status=status,
        )

    def preparar_cenario(
        self,
        *,
        scenario: str,
        status_ad: str,
        status_vpn: str = "NP",
    ) -> tuple[Colaborador, Ferias]:
        colaborador = self.criar_colaborador_teste()
        datas = self.scenario_dates(scenario)
        ferias = self.criar_ferias(
            colaborador,
            data_saida=datas.data_saida,
            data_retorno=datas.data_retorno,
        )
        self.criar_acesso(
            colaborador,
            sistema=self.ad_system_name,
            status=status_ad,
        )
        self.criar_acesso(
            colaborador,
            sistema=self.vpn_system_name,
            status=status_vpn,
        )
        return colaborador, ferias

    def criar_processamento(
        self,
        *,
        colaborador: Colaborador,
        acao: str,
        resultado: str,
        data_saida=None,
        data_retorno=None,
        ad_status: str = "",
        vpn_status: str = "NP",
        mensagem: str = "",
    ) -> BlockProcessing:
        return BlockProcessing.objects.create(
            colaborador_id=colaborador.id,
            usuario_ad=colaborador.login_ad or "",
            email=colaborador.email or "",
            acao=acao,
            data_saida=data_saida,
            data_retorno=data_retorno,
            ad_status=ad_status,
            vpn_status=vpn_status,
            resultado=resultado,
            mensagem=mensagem,
        )

    def configurar_block(self, *, dry_run: bool = False, usuario_teste_ad: str | None = None) -> BlockConfig:
        return BlockConfig.objects.create(
            nome="Configuracao Teste",
            usuario_teste_ad=usuario_teste_ad or self.usuario_ad_teste,
            ativo=True,
            dry_run=dry_run,
        )
