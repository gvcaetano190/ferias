from typing import Any, Dict
from apps.block.business_service import BlockBusinessService

def run_operational_verification() -> Dict[str, Any]:
    """
    Task agendada para popular a fila operacional (preflight).
    Consulta o AD e prepara a lista de quem precisa de bloqueio/desbloqueio hoje.
    """
    service = BlockBusinessService()
    return service.processar_verificacao_operacional_block()

def run_block_verification() -> Dict[str, Any]:
    """
    Task agendada para processar efetivamente os bloqueios e desbloqueios.
    Utiliza a fila operacional e aplica as chamadas no Active Directory.
    """
    service = BlockBusinessService()
    return service.processar_verificacao_block()
