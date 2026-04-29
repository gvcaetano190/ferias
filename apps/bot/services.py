"""
Bot service for WhatsApp commands.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from django.utils import timezone

logger = logging.getLogger(__name__)

MESES = {
    "janeiro": 1,
    "jan": 1,
    "fevereiro": 2,
    "fev": 2,
    "marco": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "maio": 5,
    "mai": 5,
    "junho": 6,
    "jun": 6,
    "julho": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "setembro": 9,
    "set": 9,
    "outubro": 10,
    "out": 10,
    "novembro": 11,
    "nov": 11,
    "dezembro": 12,
    "dez": 12,
}

NOMES_MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Marco",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

MENSAGEM_AJUDA = (
    "🤖 *Menu de Ajuda do Bot*\n\n"
    "Não entendeu? Tudo bem! Aqui está o que eu sei fazer:\n\n"
    "🔍 *Buscar Colaborador*\n"
    "_(Traz a ficha completa com e-mail, login AD, férias e status VPN/AD)_\n"
    "→ Digite: *buscar joao* ou *buscar joao@email.com*\n\n"
    "👮 *Buscar Gestor*\n"
    "_(Localiza quem é o chefe de alguém e traz o e-mail dele)_\n"
    "→ Digite: *gestor gabriel* ou *gestor gabriel@email.com*\n\n"
    "🧾 *Consultar Totvs*\n"
    "_(Consulta o status real da pessoa no TOTVS por nome, e-mail ou login)_\n"
    "→ Digite: *totvs gabriel.caetano* ou *totvs gabriel@email.com*\n\n"
    "🔒 *Bloquear no Totvs*\n"
    "_(Bloqueia a pessoa no TOTVS por nome, e-mail ou login)_\n"
    "→ Digite: *totvs bloquear gabriel.caetano*\n\n"
    "🔓 *Desbloquear no Totvs*\n"
    "_(Desbloqueia a pessoa no TOTVS por nome, e-mail ou login)_\n"
    "→ Digite: *totvs desbloquear gabriel.caetano*\n\n"
    "🔮 *Previsão de Ações do Bot*\n"
    "_(Mostra exatamente quem eu vou bloquear/desbloquear hoje em tempo real)_\n"
    "→ Digite: *previsao*\n\n"
    "📅 *Saídas e Retornos de Férias*\n"
    "→ Digite: *saidas hoje* ou *retornos hoje*\n\n"
    "🏖️ *Quem está de férias agora*\n"
    "→ Digite: *ausentes agora*\n\n"
    "📊 *Dashboard Estratégico*\n"
    "→ Mês atual: *dashboard*\n"
    "→ Mês específico: *dashboard 04* ou *dashboard abril*\n\n"
    "🔄 *Sincronizar planilha*\n"
    "→ Digite: *sincronizar*\n\n"
    "🔍 *Verificação Operacional*\n"
    "→ Digite: *verificacao*\n\n"
    "📋 *Lista Final (Bloqueio/Desbloqueio)*\n"
    "→ Digite: *lista final*\n\n"
    "▶️ *Executar Bloqueios/Desbloqueios (Manual)*\n"
    "→ Digite: *executar block*\n\n"
    "⏰ *Próximas execuções agendadas*\n"
    "→ Digite: *agenda*\n\n"
    "💡 _Você também pode usar os botões enviando um simples 'oi'!_"
)


def _fmt_lista(itens: list[dict], titulo: str) -> str:
    """Formata uma lista de colaboradores para exibicao no WhatsApp."""
    if not itens:
        return f"{titulo}: nenhum registro para hoje."

    hoje = date.today().strftime("%d/%m/%Y")
    linhas = [f"*{titulo} - {hoje}*\n"]
    for i, item in enumerate(itens, 1):
        linhas.append(f"{i}. {item['nome']} - _{item['setor']}_")
    linhas.append(f"\n*Total: {len(itens)} pessoa{'s' if len(itens) > 1 else ''}*")
    return "\n".join(linhas)


def _parse_month(text: str) -> tuple[int | None, int | None]:
    """
    Tenta extrair mes e ano de uma string.
    """
    hoje = date.today()

    for nome, num in MESES.items():
        if nome in text:
            match = re.search(rf"{nome}\s+(\d{{4}})", text)
            year = int(match.group(1)) if match else hoje.year
            return num, year

    match = re.search(r"\b(\d{1,2})(?:/(\d{4}))?\b", text)
    if match:
        month = int(match.group(1))
        year = int(match.group(2)) if match.group(2) else hoje.year
        if 1 <= month <= 12:
            return month, year

    return None, None


def _format_schedule_datetime(value) -> str:
    if not value:
        return "-"
    try:
        localized = timezone.localtime(value) if timezone.is_aware(value) else value
        return localized.strftime("%d/%m/%Y as %H:%M")
    except Exception:
        return str(value)


class BotService:
    def handle(self, sender: str, text: str) -> None:
        """
        Recebe a mensagem, identifica o comando e responde pelo provider.
        """
        normalized = text.lower().strip()
        logger.info("[Bot] Mensagem de %s: %r", sender, text)

        command = self._parse_command(normalized)
        logger.info("[Bot] Comando identificado: %r", command)

        self._execute(sender, command, normalized)

    def _parse_command(self, text: str) -> str:
        if text.startswith("buscar "):
            return "buscar_colaborador"

        if text.startswith("gestor "):
            return "buscar_gestor"

        if text.startswith("totvs bloquear "):
            return "bloquear_totvs"

        if (
            text.startswith("totvs desbloquear ")
            or text.startswith("totvs desbloquear ")
            or text.startswith("totvs desbloquar ")
        ):
            return "desbloquear_totvs"

        if text.startswith("totvs "):
            return "consultar_totvs"

        if any(word in text for word in ["previsao", "previsão", "previsão de hoje", "🔮 previsão"]):
            return "previsao_hoje"

        if any(word in text for word in ["sincronizar", "sincroniza", "sync", "atualizar planilha"]):
            return "sincronizar"

        if any(word in text for word in ["verificacao", "verificacao operacional", "operacional", "preflight"]):
            return "verificacao_operacional"

        execution_aliases = {"block", "desblok", "desblock"}
        execution_verbs = ["executar", "rodar", "aplicar", "processar", "run"]
        if text.strip() in execution_aliases:
            return "executar_block"
        if "aplicar fila final" in text:
            return "executar_block"
        if any(alias in text for alias in execution_aliases) and any(verb in text for verb in execution_verbs):
            return "executar_block"

        if any(word in text for word in ["lista final", "fila", "bloqueio", "desbloqueio"]):
            return "lista_final"

        if any(word in text for word in ["agenda", "tasks", "proxima", "agendamento"]):
            return "agenda"

        if any(word in text for word in ["dashboard", "relatorio", "print", "foto"]):
            return "dashboard"

        if any(word in text for word in ["sai", "saida", "saidah", "saindo"]):
            if any(word in text for word in ["hj", "hoje", "today"]):
                return "saidas_hoje"

        if any(word in text for word in ["volta", "retorno", "voltando", "retornou"]):
            if any(word in text for word in ["hj", "hoje", "today"]):
                return "retornos_hoje"

        if any(word in text for word in ["ausente", "fora agora", "ferias agora", "esta de ferias", "quem ta"]):
            return "ausentes_agora"

        if any(word in text for word in ["ajuda", "help", "comandos", "oi", "ola", "menu"]):
            return "ajuda"

        return "desconhecido"

    def _execute(self, sender: str, command: str, original_text: str) -> None:
        from apps.bot.queries import BotQueryService

        queries = BotQueryService()

        if command == "saidas_hoje":
            itens = queries.saidas_hoje()
            self._reply_text(sender, _fmt_lista(itens, "Saidas de hoje"))
        elif command == "retornos_hoje":
            itens = queries.retornos_hoje()
            self._reply_text(sender, _fmt_lista(itens, "Retornos de hoje"))
        elif command == "ausentes_agora":
            itens = queries.ausentes_agora()
            self._reply_text(sender, _fmt_lista(itens, "Em ferias agora"))
        elif command == "dashboard":
            month, year = _parse_month(original_text)
            self._reply_dashboard(sender, month=month, year=year)
        elif command == "sincronizar":
            self._reply_sincronizar(sender)
        elif command == "verificacao_operacional":
            self._reply_verificacao_operacional(sender)
        elif command == "executar_block":
            self._reply_executar_block(sender)
        elif command == "lista_final":
            self._reply_lista_final(sender)
        elif command == "buscar_colaborador":
            termo = original_text.lower().replace("buscar ", "", 1).strip()
            self._reply_buscar_colaborador(sender, termo)
        elif command == "buscar_gestor":
            termo = original_text.lower().replace("gestor ", "", 1).strip()
            self._reply_buscar_gestor(sender, termo)
        elif command == "bloquear_totvs":
            termo = original_text[len("totvs bloquear "):].strip()
            self._reply_alterar_totvs(sender, termo, active=False)
        elif command == "desbloquear_totvs":
            termo = original_text
            for prefixo in ("totvs desbloquear ", "totvs desbloquear ", "totvs desbloquar "):
                if termo.startswith(prefixo):
                    termo = termo[len(prefixo):].strip()
                    break
            self._reply_alterar_totvs(sender, termo, active=True)
        elif command == "consultar_totvs":
            termo = original_text[6:].strip()
            self._reply_consultar_totvs(sender, termo)
        elif command == "previsao_hoje":
            self._reply_previsao_hoje(sender)
        elif command == "agenda":
            self._reply_agenda(sender)
        elif command == "ajuda":
            self._reply_menu(sender)
        else:
            self._reply_menu(sender)

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
            logger.error("[Bot] Falha ao enviar texto: %s", result.message)

    def _reply_buscar_colaborador(self, sender: str, termo: str) -> None:
        from apps.bot.queries import BotQueryService
        queries = BotQueryService()
        dados = queries.buscar_colaborador(termo)
        
        if not dados:
            self._reply_text(sender, f"❌ Não encontrei nenhum colaborador com o termo: '{termo}'.")
            return
            
        ferias_txt = "Nenhuma programada futuramente"
        if dados['ferias_saida']:
            saida = dados['ferias_saida'].strftime('%d/%m/%Y')
            retorno = dados['ferias_retorno'].strftime('%d/%m/%Y')
            ferias_txt = f"Sai {saida}, Volta {retorno}"
            
        msg = (
            f"👤 *{dados['nome']}*\n"
            f"📧 Email: {dados['email'] or '—'}\n"
            f"💻 Login AD: {dados['login_ad'] or '—'}\n"
            f"🏢 Setor: {dados['departamento'] or '—'}\n"
            f"👮 Gestor: {dados['gestor'] or '—'}\n"
            f"🏖️ Férias: {ferias_txt}\n\n"
            f"🔒 VPN: {dados['status_vpn']}\n"
            f"🔒 AD: {dados['status_ad']}"
        )
        self._reply_text(sender, msg)

    def _reply_buscar_gestor(self, sender: str, termo: str) -> None:
        from apps.bot.queries import BotQueryService
        queries = BotQueryService()
        dados = queries.buscar_gestor(termo)
        
        if not dados:
            self._reply_text(sender, f"❌ Não consegui achar gestor para '{termo}'.")
            return
            
        msg = (
            f"Colaborador: *{dados['colaborador_nome']}*\n"
            f"👮 *Gestor:* {dados['gestor_nome']}\n"
            f"📧 *Email do Gestor:* {dados['gestor_email']}"
        )
        self._reply_text(sender, msg)

    def _reply_consultar_totvs(self, sender: str, termo: str) -> None:
        from apps.bot.queries import BotQueryService
        from apps.totvs.services import TotvsIntegrationService
        from integrations.totvs.client import TotvsClientError

        termo = (termo or "").strip()
        if not termo:
            self._reply_text(sender, "Informe um nome, e-mail ou login depois de 'totvs'.")
            return

        queries = BotQueryService()
        colaborador = queries.localizar_colaborador(termo)
        if not colaborador:
            self._reply_text(sender, f"Nao encontrei colaborador para '{termo}'.")
            return

        service = TotvsIntegrationService()
        try:
            resolved = service.consultar_usuario(colaborador.login_ad or colaborador.email or termo)
            status = "DESBLOQUEADO" if resolved.active else "BLOQUEADO"
        except TotvsClientError as exc:
            if exc.status_code == 404:
                status = "NAO ENCONTRADO"
            else:
                self._reply_text(sender, f"Falha ao consultar TOTVS para {colaborador.nome}: {exc}")
                return

        msg = (
            f"🧾 Totvs - {colaborador.nome}\n"
            f"STATUS: {status}"
        )
        self._reply_text(sender, msg)

    def _reply_alterar_totvs(self, sender: str, termo: str, *, active: bool) -> None:
        from apps.bot.queries import BotQueryService
        from apps.totvs.services import TotvsIntegrationService
        from integrations.totvs.client import TotvsClientError

        termo = (termo or "").strip()
        if not termo:
            self._reply_text(sender, "Informe um nome, e-mail ou login depois do comando do TOTVS.")
            return

        queries = BotQueryService()
        colaborador = queries.localizar_colaborador(termo)
        if not colaborador:
            self._reply_text(sender, f"Nao encontrei colaborador para '{termo}'.")
            return

        service = TotvsIntegrationService()
        try:
            resolved = service.atualizar_status_usuario(
                identifier=colaborador.login_ad or colaborador.email or termo,
                active=active,
            )
            status = "DESBLOQUEADO" if resolved.active else "BLOQUEADO"
        except TotvsClientError as exc:
            if exc.status_code == 404:
                status = "NAO ENCONTRADO"
                self._reply_text(sender, f"🧾 Totvs - {colaborador.nome}\nSTATUS: {status}")
                return
            self._reply_text(sender, f"Falha ao alterar TOTVS para {colaborador.nome}: {exc}")
            return

        self._reply_text(sender, f"🧾 Totvs - {colaborador.nome}\nSTATUS: {status}")

    def _reply_previsao_hoje(self, sender: str) -> None:
        try:
            from apps.block.preview_service import BlockPreviewService
            service = BlockPreviewService()
            data = service.previsualizar_verificacao_block()
            
            rows = data.get("rows", [])
            summary = data.get("summary", {})
            
            if not rows:
                self._reply_text(sender, "🔮 *Previsão de Hoje*\nNenhuma ação de bloqueio ou desbloqueio pendente para hoje na prévia.")
                return
                
            msg = (
                "🔮 *Previsão de Bloqueios/Desbloqueios de Hoje*\n\n"
                f"*Resumo*: {summary.get('bloquear', 0)} para Bloquear | {summary.get('desbloquear', 0)} para Desbloquear\n\n"
            )
            
            for item in rows[:15]:
                acao = item.get("acao_prevista", "—")
                icone = "🔒" if acao == "BLOQUEAR" else "🔓" if acao == "DESBLOQUEAR" else "➖"
                msg += f"{icone} {acao}: {item['colaborador']}\n"
                
            if len(rows) > 15:
                msg += f"\n... e mais {len(rows) - 15} itens."
                
            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro ao buscar previsão: %s", exc)
            self._reply_text(sender, f"Erro ao buscar previsão: {exc}")

    def _reply_menu(self, sender: str) -> None:
        """Envia o menu interativo com os comandos mais comuns."""
        provider = self._get_provider()
        if not provider:
            return
        
        # O Provider Evolution tem suporte nativo para _send_buttons
        if hasattr(provider, "send_buttons"):
            botoes = [
                {"id": "btn_previsao", "text": "🔮 Previsão de Hoje"},
                {"id": "btn_sync", "text": "🔄 Sincronizar"},
                {"id": "btn_dashboard", "text": "📊 Ver Dashboard"}
            ]
            
            result = provider.send_buttons(
                destination=sender,
                text="🤖 *Menu Principal*\nEscolha uma das opções rápidas abaixo ou digite o que precisa (ex: _buscar joão_, _gestor maria_):",
                buttons=botoes,
                footer="Gestão de Férias e Acessos"
            )
            if result.success:
                return
            else:
                logger.warning("[Bot] Falha ao enviar botões: %s. Tentando texto.", result.message)
                
        # Fallback para texto caso a API de botões falhe ou não suporte
        self._reply_text(sender, MENSAGEM_AJUDA)

    def _reply_dashboard(self, sender: str, month: int | None, year: int | None) -> None:
        """Gera o screenshot do dashboard e envia como imagem."""
        from datetime import date as _date

        from apps.reports.screenshot import DashboardScreenshotService

        hoje = _date.today()
        month = month or hoje.month
        year = year or hoje.year
        nome_mes = NOMES_MESES.get(month, str(month))

        self._reply_text(sender, f"Gerando dashboard de *{nome_mes} {year}*...")

        try:
            jpeg_bytes = DashboardScreenshotService().generate(month=month, year=year)
        except Exception as exc:
            logger.exception("[Bot] Erro ao gerar screenshot: %s", exc)
            self._reply_text(sender, "Erro ao gerar o dashboard. Tente novamente.")
            return

        provider = self._get_provider()
        if not provider:
            return

        caption = f"Dashboard Estrategico - {nome_mes} {year}"
        result = provider.send_image(
            destination=sender,
            image_bytes=jpeg_bytes,
            caption=caption,
        )
        if not result.success:
            logger.error("[Bot] Falha ao enviar imagem: %s", result.message)
            self._reply_text(sender, "Erro ao enviar a imagem. Tente novamente.")

    def _reply_sincronizar(self, sender: str) -> None:
        """Executa a sincronizacao da planilha e retorna o resultado."""
        self._reply_text(sender, "Sincronizando planilha... isso pode levar alguns segundos.")

        try:
            from apps.sync.tasks import run_spreadsheet_sync

            result = run_spreadsheet_sync(notify=False)
            status = result.get("status", "desconhecido")
            total = result.get("total_registros", result.get("total", "?"))

            msg = (
                "*Sincronizacao concluida!*\n\n"
                f"Status: {status}\n"
                f"Registros processados: {total}"
            )

            for key in ["inseridos", "atualizados", "removidos", "created", "updated", "deleted"]:
                if key in result and result[key]:
                    msg += f"\n- {key.capitalize()}: {result[key]}"

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro na sincronizacao: %s", exc)
            self._reply_text(sender, f"Erro na sincronizacao: {exc}")

    def _reply_verificacao_operacional(self, sender: str) -> None:
        """Executa a verificacao operacional e retorna o resultado."""
        self._reply_text(sender, "Executando verificacao operacional...")

        try:
            from apps.block.tasks import run_operational_verification

            result = run_operational_verification(notify=False)
            msg = "*Verificacao operacional concluida!*\n\n"

            if isinstance(result, dict):
                for key, value in result.items():
                    if key != "status":
                        label = key.replace("_", " ").capitalize()
                        msg += f"- {label}: {value}\n"
            else:
                msg += f"Resultado: {result}"

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro na verificacao operacional: %s", exc)
            self._reply_text(sender, f"Erro na verificacao: {exc}")

    def _reply_lista_final(self, sender: str) -> None:
        """Consulta a lista final de bloqueio/desbloqueio e envia."""
        try:
            from apps.block.preview_service import BlockPreviewService

            service = BlockPreviewService()
            data = service.ver_detalhes_verificacao_operacional()

            if not data.get("run"):
                self._reply_text(sender, "Nenhuma verificacao operacional encontrada. Execute *verificacao* primeiro.")
                return

            lista_final = data.get("lista_final", [])
            summary = data.get("summary", {})
            msg = (
                "*Lista Final - Verificacao Operacional*\n\n"
                "*Resumo:*\n"
                f"- Total inicial: {summary.get('inicial_total', 0)}\n"
                f"- Total final: {summary.get('final_total', 0)}\n"
                f"- Bloquear: {summary.get('final_bloquear', 0)}\n"
                f"- Desbloquear: {summary.get('final_desbloquear', 0)}\n"
            )

            if lista_final:
                msg += "\n*Detalhes:*\n"
                for item in lista_final[:20]:
                    msg += f"- {item.colaborador_nome} - {item.acao_final}\n"
                if len(lista_final) > 20:
                    msg += f"\n... e mais {len(lista_final) - 20} itens"
            else:
                msg += "\nNenhuma acao pendente na fila."

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro ao buscar lista final: %s", exc)
            self._reply_text(sender, f"Erro ao buscar lista final: {exc}")

    def _reply_executar_block(self, sender: str) -> None:
        """Executa a fila final de bloqueio/desbloqueio."""
        self._reply_text(sender, "Executando block/desblok na fila final...")

        try:
            from apps.block.tasks import run_block_verification

            result = run_block_verification(
                notify=False,
                require_operational_queue=True,
            )

            if result.get("skipped"):
                self._reply_text(
                    sender,
                    "Nenhuma fila final pronta para executar. Rode *verificacao* primeiro.",
                )
                return

            titulo = "Simulacao concluida" if result.get("dry_run") else "Execucao final concluida"
            msg = (
                f"*{titulo}!*\n\n"
                f"Bloqueios: {result.get('bloqueios_feitos', 0)}\n"
                f"Desbloqueios: {result.get('desbloqueios_feitos', 0)}\n"
                f"Sincronizados: {result.get('sincronizados', 0)}\n"
                f"Ignorados: {result.get('ignorados', 0)}\n"
                f"Erros: {result.get('erros', 0)}"
            )

            if result.get("used_operational_queue"):
                msg += "\n\nFila operacional aplicada com sucesso."

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro na execucao final do block: %s", exc)
            self._reply_text(sender, f"Erro ao executar o block/desblok: {exc}")

    def _reply_agenda(self, sender: str) -> None:
        """Consulta as tasks agendadas no Django-Q2 e mostra proximas execucoes."""
        try:
            from django_q.models import Schedule

            schedules = Schedule.objects.all().order_by("next_run")
            if not schedules.exists():
                self._reply_text(sender, "Nenhuma task agendada encontrada.")
                return

            agora = timezone.localtime().strftime("%d/%m/%Y %H:%M")
            msg = f"*Agenda de Tasks - {agora}*\n"

            for schedule in schedules:
                status_icon = "OK" if schedule.repeats != 0 else "PAUSADA"
                next_run = _format_schedule_datetime(schedule.next_run)
                tipo = str(schedule.schedule_type) if schedule.schedule_type else "-"
                repeats = "infinito" if schedule.repeats == -1 else schedule.repeats
                msg += (
                    f"\n{status_icon} *{schedule.name}*\n"
                    f"  Proxima: {next_run}\n"
                    f"  Tipo: {tipo}\n"
                    f"  Repeticoes: {repeats}\n"
                )

            self._reply_text(sender, msg)
        except Exception as exc:
            logger.exception("[Bot] Erro ao buscar agenda: %s", exc)
            self._reply_text(sender, f"Erro ao buscar agenda: {exc}")
