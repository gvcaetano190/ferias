from __future__ import annotations

from apps.block.preview_service import BlockPreviewService
from apps.block.business_service import BlockBusinessService, BlockServiceResult

# Keep BlockService for backward compatibility if anyone imports it, 
# but internally delegate to the new specific services.
# Or just leave it as an empty file if no one else imports it.
# We'll expose the result dataclass just in case.

class BlockService:
    def __init__(self):
        self.preview_service = BlockPreviewService()
        self.business_service = BlockBusinessService()

    def previsualizar_verificacao_block(self):
        return self.preview_service.previsualizar_verificacao_block()

    def ver_detalhes_verificacao_operacional(self, **kwargs):
        return self.preview_service.ver_detalhes_verificacao_operacional(**kwargs)

    def dashboard_data(self):
        return self.preview_service.dashboard_data()

    def dashboard_data_filtrada(self, **kwargs):
        return self.preview_service.dashboard_data_filtrada(**kwargs)

    def processar_verificacao_block(self, **kwargs):
        return self.business_service.processar_verificacao_block(**kwargs)

    def processar_verificacao_operacional_block(self, **kwargs):
        return self.business_service.processar_verificacao_operacional_block(**kwargs)

    def processar_bloqueios(self, *args, **kwargs):
        return self.business_service.processar_bloqueios(*args, **kwargs)

    def processar_desbloqueios(self, *args, **kwargs):
        return self.business_service.processar_desbloqueios(*args, **kwargs)

    def testar_bloqueio(self):
        return self.business_service.testar_bloqueio()

    def testar_desbloqueio(self):
        return self.business_service.testar_desbloqueio()
