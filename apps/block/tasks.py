from typing import Any, Dict

from apps.block.business_service import BlockBusinessService


def run_operational_verification(*, notify: bool = True) -> Dict[str, Any]:
    """
    Task agendada para popular a fila operacional (preflight).
    Consulta o AD e prepara a lista de quem precisa de bloqueio/desbloqueio hoje.
    """
    service = BlockBusinessService()
    return service.processar_verificacao_operacional_block(notify=notify)


def run_block_verification(
    *,
    notify: bool = True,
    require_operational_queue: bool = False,
) -> Dict[str, Any]:
    """
    Task agendada para processar efetivamente os bloqueios e desbloqueios.
    Utiliza a fila operacional e aplica as chamadas no Active Directory.
    """
    service = BlockBusinessService()
    return service.processar_verificacao_block(
        notify=notify,
        require_operational_queue=require_operational_queue,
    )
