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
  - "sincronizar" / "sync"              → sincroniza a planilha
  - "verificacao" / "operacional"       → roda verificação operacional
  - "lista final" / "fila"              → mostra a fila de bloqueio/desbloqueio
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
    "🔄 *Sincronizar planilha*\n"
    "  → sincronizar / sync\n\n"
    "🔍 *Verificação operacional*\n"
    "  → verificacao / operacional\n\n"
    "📋 *Lista final (bloqueio/desbloqueio)*\n"
    "  → lista final / fila\n\n"
    "⏰ *Próximas execuções agendadas*\n"
    "  → agenda / tasks / proxima\n\n"
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
        # Sincronizar planilha
        if any(w in text for w in ["sincronizar", "sincroniza", "sync", "atualizar planilha"]):
            return "sincronizar"

        # Verificação operacional
        if any(w in text for w in ["verificacao", "verificação", "operacional", "preflight"]):
            return "verificacao_operacional"

        # Lista final de bloqueio/desbloqueio
        if any(w in text for w in ["lista final", "fila", "bloqueio", "desbloqueio"]):
            return "lista_final"

        # Agenda de tasks
        if any(w in text for w in ["agenda", "tasks", "proxima", "próxima", "agendamento"]):
            return "agenda"

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

        elif command == "sincronizar":
            self._reply_sincronizar(sender)

        elif command == "verificacao_operacional":
            self._reply_verificacao_operacional(sender)

        elif command == "lista_final":
            self._reply_lista_final(sender)

        elif command == "agenda":
            self._reply_agenda(sender)

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

    def _reply_sincronizar(self, sender: str) -> None:
        """Executa a sincronização da planilha e retorna o resultado."""
        self._reply_text(sender, "⏳ Sincronizando planilha... isso pode levar alguns segundos.")

        try:
            from apps.sync.tasks import run_spreadsheet_sync
            result = run_spreadsheet_sync()

            status = result.get("status", "desconhecido")
            total = result.get("total_registros", result.get("total", "?"))
            msg = (
                f"✅ *Sincronização concluída!*\n\n"
                f"📄 Status: {status}\n"
                f"📊 Registros processados: {total}"
            )

            # Adiciona detalhes extras se existirem
            for key in ["inseridos", "atualizados", "removidos", "created", "updated", "deleted"]:
                if key in result and result[key]:
                    label = key.capitalize()
                    msg += f"\n  • {label}: {result[key]}"

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception(f"[Bot] Erro na sincronização: {exc}")
            self._reply_text(sender, f"❌ Erro na sincronização: {exc}")

    def _reply_verificacao_operacional(self, sender: str) -> None:
        """Executa a verificação operacional e retorna o resultado."""
        self._reply_text(sender, "⏳ Executando verificação operacional...")

        try:
            from apps.block.tasks import run_operational_verification
            result = run_operational_verification()

            msg = "✅ *Verificação operacional concluída!*\n\n"

            if isinstance(result, dict):
                for key, value in result.items():
                    if key != "status":
                        label = key.replace("_", " ").capitalize()
                        msg += f"  • {label}: {value}\n"
            else:
                msg += f"Resultado: {result}"

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception(f"[Bot] Erro na verificação operacional: {exc}")
            self._reply_text(sender, f"❌ Erro na verificação: {exc}")

    def _reply_lista_final(self, sender: str) -> None:
        """Consulta a lista final de bloqueio/desbloqueio e envia."""
        try:
            from apps.block.preview_service import BlockPreviewService
            service = BlockPreviewService()
            data = service.ver_detalhes_verificacao_operacional()

            if not data.get("run"):
                self._reply_text(sender, "⚠️ Nenhuma verificação operacional encontrada. Execute *verificacao* primeiro.")
                return

            lista_final = data.get("lista_final", [])
            summary = data.get("summary", {})

            msg = (
                f"📋 *Lista Final — Verificação Operacional*\n\n"
                f"📊 *Resumo:*\n"
                f"  • Total inicial: {summary.get('inicial_total', 0)}\n"
                f"  • Total final: {summary.get('final_total', 0)}\n"
                f"  • 🔒 Bloquear: {summary.get('final_bloquear', 0)}\n"
                f"  • 🔓 Desbloquear: {summary.get('final_desbloquear', 0)}\n"
            )

            if lista_final:
                msg += "\n*Detalhes:*\n"
                for item in lista_final[:20]:  # Limita a 20 itens no WhatsApp
                    emoji = "🔒" if item.acao_final == "BLOQUEAR" else "🔓"
                    msg += f"{emoji} {item.colaborador_nome} — {item.acao_final}\n"

                if len(lista_final) > 20:
                    msg += f"\n_... e mais {len(lista_final) - 20} itens_"
            else:
                msg += "\n✅ Nenhuma ação pendente na fila."

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception(f"[Bot] Erro ao buscar lista final: {exc}")
            self._reply_text(sender, f"❌ Erro ao buscar lista final: {exc}")

    def _reply_agenda(self, sender: str) -> None:
        """Consulta as tasks agendadas no Django-Q2 e mostra próximas execuções."""
        try:
            from django_q.models import Schedule
            from datetime import datetime

            schedules = Schedule.objects.all().order_by("next_run")

            if not schedules.exists():
                self._reply_text(sender, "⚠️ Nenhuma task agendada encontrada.")
                return

            agora = datetime.now().strftime("%d/%m/%Y %H:%M")
            msg = f"⏰ *Agenda de Tasks — {agora}*\n"

            for s in schedules:
                status_icon = "✅" if s.repeats != 0 else "⏸️"

                if s.next_run:
                    next_run = s.next_run.strftime("%d/%m/%Y às %H:%M")
                else:
                    next_run = "—"

                if s.last_run:
                    last_run = s.last_run.strftime("%d/%m %H:%M")
                else:
                    last_run = "nunca"

                msg += (
                    f"\n{status_icon} *{s.name}*\n"
                    f"  📌 Próxima: {next_run}\n"
                    f"  🕐 Última: {last_run}\n"
                    f"  🔁 Tipo: {s.schedule_type}\n"
                )

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception(f"[Bot] Erro ao buscar agenda: {exc}")
            self._reply_text(sender, f"❌ Erro ao buscar agenda: {exc}")

