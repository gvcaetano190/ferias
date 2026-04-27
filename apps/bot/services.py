"""
BotService
==========
Interpreta mensagens WhatsApp e responde com texto ou imagem do dashboard.

Comandos suportados:
  - "quem sai hoje" / "saidas hj"       → lista de saídas de hoje
  - "quem volta hoje" / "retornos hj"   → lista de retornos de hoje
  - "quem esta de ferias" / "ausentes"  → quem está fora agora
  - "dashboard" / "relatorio"           → screenshot do mês atual
  - "dashboard de abril" / "dashboard 04" → screenshot de um mês específico
  - "ajuda" / "help"                    → lista de comandos
"""
from __future__ import annotations

import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

# Mapeamento de nomes de mês (pt-br) para número
MESES = {
    "janeiro": 1, "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4, "abr": 4,
    "maio": 5, "mai": 5,
    "junho": 6, "jun": 6,
    "julho": 7, "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9, "set": 9,
    "outubro": 10, "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

NOMES_MESES = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

MENSAGEM_AJUDA = (
    "🤖 *Comandos disponíveis:*\n\n"
    "📅 *Saídas de hoje*\n"
    "  → quem sai hoje / saidas hj\n\n"
    "🔄 *Retornos de hoje*\n"
    "  → quem volta hoje / retornos hj\n\n"
    "🏖️ *Quem está de férias agora*\n"
    "  → quem esta de ferias / ausentes agora\n\n"
    "📊 *Dashboard do mês atual*\n"
    "  → dashboard / relatorio\n\n"
    "📊 *Dashboard de um mês específico*\n"
    "  → dashboard de abril / relatorio 04\n\n"
    "❓ *Esta ajuda*\n"
    "  → ajuda / help"
)


def _fmt_lista(itens: list[dict], titulo: str) -> str:
    """Formata uma lista de colaboradores para exibição no WhatsApp."""
    if not itens:
        return f"✅ {titulo}: nenhum registro para hoje."
    hoje = date.today().strftime("%d/%m/%Y")
    linhas = [f"📋 *{titulo} — {hoje}*\n"]
    for i, item in enumerate(itens, 1):
        linhas.append(f"{i}. {item['nome']} — _{item['setor']}_")
    linhas.append(f"\n*Total: {len(itens)} pessoa{'s' if len(itens) > 1 else ''}*")
    return "\n".join(linhas)


def _parse_month(text: str) -> tuple[int | None, int | None]:
    """
    Tenta extrair mês e ano de uma string.
    Suporta:
      - "dashboard de abril"         → (4, ano_atual)
      - "dashboard 04"               → (4, ano_atual)
      - "dashboard 04/2026"          → (4, 2026)
    Retorna (None, None) se não encontrar.
    """
    hoje = date.today()

    # Verifica nome de mês em português
    for nome, num in MESES.items():
        if nome in text:
            # Tenta extrair o ano junto, ex: "abril 2026"
            m = re.search(rf"{nome}\s+(\d{{4}})", text)
            year = int(m.group(1)) if m else hoje.year
            return num, year

    # Verifica número: "04", "04/2026", "4"
    m = re.search(r"\b(\d{1,2})(?:/(\d{4}))?\b", text)
    if m:
        month = int(m.group(1))
        year = int(m.group(2)) if m.group(2) else hoje.year
        if 1 <= month <= 12:
            return month, year

    return None, None


class BotService:

    def handle(self, sender: str, text: str) -> None:
        """
        Ponto de entrada: recebe o número do remetente e o texto da mensagem.
        Interpreta o comando e envia a resposta de volta via WhatsApp.
        """
        normalized = text.lower().strip()
        logger.info(f"[Bot] Mensagem de {sender}: {text!r}")

        command = self._parse_command(normalized)
        logger.info(f"[Bot] Comando identificado: {command!r}")

        self._execute(sender, command, normalized)

    # ── Parser ──────────────────────────────────────────────────────────────

    def _parse_command(self, text: str) -> str:
        # Dashboard / screenshot
        if any(w in text for w in ["dashboard", "relatorio", "relatório", "print", "foto"]):
            return "dashboard"

        # Saídas de hoje
        if any(w in text for w in ["sai", "saída", "saida", "saidah", "saindo"]):
            if any(w in text for w in ["hj", "hoje", "today"]):
                return "saidas_hoje"

        # Retornos de hoje
        if any(w in text for w in ["volta", "retorno", "voltando", "retornou"]):
            if any(w in text for w in ["hj", "hoje", "today"]):
                return "retornos_hoje"

        # Quem está de férias agora
        if any(w in text for w in ["ausente", "fora agora", "ferias agora", "está de ferias", "esta de ferias", "quem ta"]):
            return "ausentes_agora"

        # Ajuda
        if any(w in text for w in ["ajuda", "help", "comandos", "oi", "ola", "olá", "menu"]):
            return "ajuda"

        return "desconhecido"

    # ── Executor ─────────────────────────────────────────────────────────────

    def _execute(self, sender: str, command: str, original_text: str) -> None:
        from apps.bot.queries import BotQueryService
        queries = BotQueryService()

        if command == "saidas_hoje":
            itens = queries.saidas_hoje()
            self._reply_text(sender, _fmt_lista(itens, "Saídas de hoje"))

        elif command == "retornos_hoje":
            itens = queries.retornos_hoje()
            self._reply_text(sender, _fmt_lista(itens, "Retornos de hoje"))

        elif command == "ausentes_agora":
            itens = queries.ausentes_agora()
            self._reply_text(sender, _fmt_lista(itens, "Em férias agora"))

        elif command == "dashboard":
            month, year = _parse_month(original_text)
            self._reply_dashboard(sender, month=month, year=year)

        elif command == "ajuda":
            self._reply_text(sender, MENSAGEM_AJUDA)

        else:
            self._reply_text(
                sender,
                "❓ Não entendi o comando.\nDigite *ajuda* para ver o que posso fazer.",
            )

    # ── Respostas ────────────────────────────────────────────────────────────

    def _get_provider(self):
        """Carrega o provider Evolution API ativo do banco."""
        from apps.notifications.models import NotificationProviderConfig
        from apps.notifications.providers.evolution import EvolutionWhatsAppProvider

        cfg = (
            NotificationProviderConfig.objects
            .filter(enabled=True, provider_type=NotificationProviderConfig.TYPE_EVOLUTION)
            .first()
        )
        if not cfg:
            logger.error("[Bot] Nenhum provider Evolution API ativo encontrado.")
            return None

        return EvolutionWhatsAppProvider(
            endpoint_url=cfg.endpoint_url,
            api_key=cfg.api_key,
            timeout_seconds=cfg.timeout_seconds,
        )

    def _reply_text(self, sender: str, text: str) -> None:
        provider = self._get_provider()
        if not provider:
            return
        result = provider.send_text(destination=sender, text=text)
        if not result.success:
            logger.error(f"[Bot] Falha ao enviar texto: {result.message}")

    def _reply_dashboard(self, sender: str, month: int | None, year: int | None) -> None:
        """Gera o screenshot do dashboard e envia como imagem."""
        from apps.reports.screenshot import DashboardScreenshotService
        from datetime import date as _date

        hoje = _date.today()
        month = month or hoje.month
        year = year or hoje.year
        nome_mes = NOMES_MESES.get(month, str(month))

        # Avisa que está gerando (pode levar alguns segundos)
        self._reply_text(sender, f"⏳ Gerando dashboard de *{nome_mes} {year}*...")

        try:
            jpeg_bytes = DashboardScreenshotService().generate(month=month, year=year)
        except Exception as exc:
            logger.exception(f"[Bot] Erro ao gerar screenshot: {exc}")
            self._reply_text(sender, "❌ Erro ao gerar o dashboard. Tente novamente.")
            return

        provider = self._get_provider()
        if not provider:
            return

        caption = f"📊 Dashboard Estratégico — {nome_mes} {year}"
        result = provider.send_image(
            destination=sender,
            image_bytes=jpeg_bytes,
            caption=caption,
        )
        if not result.success:
            logger.error(f"[Bot] Falha ao enviar imagem: {result.message}")
            self._reply_text(sender, "❌ Erro ao enviar a imagem. Tente novamente.")
