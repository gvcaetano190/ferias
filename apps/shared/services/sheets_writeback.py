import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from django.conf import settings
from google.oauth2.service_account import Credentials

from apps.core.models import OperationalSettings
from apps.shared.services.google_sheets import extract_sheet_id

logger = logging.getLogger(__name__)


class GoogleSheetsWritebackService:
    """
    Servico para atualizar o status operacional (AD, VPN, TOTVS, etc)
    diretamente na planilha do Google Sheets via API (gspread).
    """

    def __init__(self):
        self.operational_settings = OperationalSettings.get_solo()
        self.credentials_path = settings.BASE_DIR / "credenciais.json"
        self.client = None
        self._authenticate()

    def _authenticate(self):
        if not self.credentials_path.exists():
            logger.warning("credenciais.json nao encontrado na raiz do projeto. Writeback ignorado.")
            return

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        try:
            creds = Credentials.from_service_account_file(str(self.credentials_path), scopes=scopes)
            self.client = gspread.authorize(creds)
        except Exception as e:
            logger.exception("Falha ao autenticar no Google Sheets: %s", e)

    def is_configured(self) -> bool:
        if not self.client:
            return False
        url = self.operational_settings.google_sheets_url or getattr(settings, "GOOGLE_SHEETS_URL", "")
        if not url:
            return False
        return bool(extract_sheet_id(url))

    def atualizar_status(self, nome_colaborador: str, atualizacoes: dict[str, str], mes_ref: int | None = None, ano_ref: int | None = None) -> bool:
        """
        Localiza o colaborador na planilha (buscando pela coluna 'Nome') e atualiza as colunas.
        Se mes_ref e ano_ref forem passados, busca especificamente na aba daquele mes/ano.
        Senao, itera das mais recentes para as mais antigas.
        """
        if not self.is_configured():
            logger.info("GoogleSheetsWritebackService nao configurado (sem client ou URL).")
            return False

        nome_alvo = (nome_colaborador or "").strip().lower()
        if not nome_alvo:
            return False

        url = self.operational_settings.google_sheets_url or getattr(settings, "GOOGLE_SHEETS_URL", "")
        sheet_id = extract_sheet_id(url)
        
        try:
            spreadsheet = self.client.open_by_key(sheet_id)
        except Exception as e:
            logger.exception("Falha ao abrir planilha pelo ID %s: %s", sheet_id, e)
            return False

        worksheets = list(spreadsheet.worksheets())
        
        # Filtra a aba se mes_ref e ano_ref foram informados
        if mes_ref and ano_ref:
            target_worksheets = [ws for ws in worksheets if self._extract_month_year(ws.title) == (mes_ref, ano_ref)]
            if target_worksheets:
                worksheets = target_worksheets
                logger.info("Filtrado abas especificas para o alvo %02d/%d: %s", mes_ref, ano_ref, [ws.title for ws in worksheets])
            else:
                logger.warning("Nenhuma aba encontrada para %02d/%d. O writeback procurara em todas.", mes_ref, ano_ref)

        # Itera pelas abas em ordem reversa (as ultimas/mais novas primeiro)
        for worksheet in reversed(worksheets):
            try:
                all_values = worksheet.get_all_values()
                if not all_values:
                    continue
                
                headers = all_values[0]
                header_lookup = {h.strip().upper(): idx for idx, h in enumerate(headers) if h}
                
                nome_col_idx = None
                for candidate in ["NOME", "FUNCIONÁRIO", "FUNCIONARIO", "COLABORADOR"]:
                    if candidate in header_lookup:
                        nome_col_idx = header_lookup[candidate]
                        break
                        
                if nome_col_idx is None:
                    continue
                    
                row_found = None
                for row_idx, row in enumerate(all_values):
                    if row_idx == 0:
                        continue # Pula o cabecalho
                    if len(row) > nome_col_idx:
                        cell_nome = str(row[nome_col_idx]).strip().lower()
                        if cell_nome == nome_alvo:
                            row_found = row_idx + 1 # +1 pois index é 0-based e Sheets é 1-based
                            break
                            
                if row_found:
                    cells_to_update = []
                    for system_name, new_status in atualizacoes.items():
                        col_name = system_name.upper()
                        if col_name in header_lookup:
                            col_idx = header_lookup[col_name] + 1
                            cells_to_update.append(
                                gspread.Cell(row=row_found, col=col_idx, value=new_status)
                            )
                    
                    if cells_to_update:
                        worksheet.update_cells(cells_to_update)
                        logger.info(
                            "Status de '%s' atualizado na aba '%s': %s", 
                            nome_colaborador, 
                            worksheet.title, 
                            atualizacoes
                        )
                        return True
                    else:
                        logger.warning("Colunas alvo nao encontradas na aba '%s'.", worksheet.title)
                        
            except Exception as e:
                logger.warning("Erro ao processar aba %s: %s", getattr(worksheet, 'title', 'desconhecida'), e)

        logger.info("Colaborador '%s' nao encontrado em nenhuma aba.", nome_colaborador)
        return False

    def _extract_month_year(self, sheet_name: str) -> tuple[int, int]:
        months = {
            "JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "MARCO": 3,
            "ABRIL": 4, "MAIO": 5, "JUNHO": 6, "JULHO": 7,
            "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
        }
        upper_name = sheet_name.upper()
        month = next((value for key, value in months.items() if key in upper_name), datetime.now().month)

        four_digits = re.search(r"(20\d{2})", sheet_name)
        if four_digits:
            return month, int(four_digits.group(1))

        two_digits = re.search(r"(\d{2})$", sheet_name)
        if two_digits:
            year = int(two_digits.group(1))
            return month, 2000 + year if year <= 30 else 1900 + year

        return month, datetime.now().year

