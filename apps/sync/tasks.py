from typing import Any, Dict

from apps.sync.services import SpreadsheetSyncService


def run_spreadsheet_sync(*, notify: bool = True) -> Dict[str, Any]:
    """
    Task agendada para baixar e sincronizar os dados da planilha
    direto para o banco de dados operacional.
    """
    service = SpreadsheetSyncService()
    return service.run(force=False, notify=notify)
