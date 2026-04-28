"""
Tarefas agendadas do Bot.
"""
from __future__ import annotations

import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def send_daily_summary(notify: bool = True) -> dict:
    """
    Gera e envia o 'Bom dia' operacional no grupo do WhatsApp, contendo o resumo
    de saídas e retornos de hoje.
    """
    logger.info("[Bot Tasks] Iniciando envio do Bom Dia Operacional...")
    
    from apps.bot.queries import BotQueryService
    from apps.bot.services import BotService
    
    queries = BotQueryService()
    saidas = queries.saidas_hoje()
    retornos = queries.retornos_hoje()
    
    msg = "☀️ *Bom dia equipe! Resumo Operacional de Hoje:*\n\n"
    
    if saidas:
        msg += f"🏖️ *{len(saidas)} pessoa(s) saindo de férias:*\n"
        for p in saidas:
            msg += f"  - {p['nome']} (_{p['setor']}_)\n"
    else:
        msg += "🏖️ Nenhuma saída de férias hoje.\n"
        
    msg += "\n"
    
    if retornos:
        msg += f"🔄 *{len(retornos)} pessoa(s) retornando hoje:*\n"
        for p in retornos:
            msg += f"  - {p['nome']} (_{p['setor']}_)\n"
    else:
        msg += "🔄 Nenhum retorno de férias hoje.\n"
        
    msg += "\n_Para sincronizar as planilhas, clique no botão do menu (Mande 'oi')._"
    
    # Pega o grupo autorizado do settings
    allowed_group = getattr(settings, "BOT_ALLOWED_GROUP", "")
    
    if notify and allowed_group:
        bot = BotService()
        bot._reply_text(allowed_group, msg)
        logger.info(f"[Bot Tasks] Bom dia enviado para o grupo: {allowed_group}")
    elif notify:
        logger.warning("[Bot Tasks] BOT_ALLOWED_GROUP não está configurado. Não é possível enviar o Bom Dia.")
        
    return {
        "status": "sucesso",
        "saidas_count": len(saidas),
        "retornos_count": len(retornos),
        "notified_group": allowed_group if notify else None
    }


def setup_daily_summary_schedule() -> None:
    """
    Configura o agendamento no Django-Q para rodar o 'Bom Dia' todo dia às 08:00 de segunda a sexta.
    """
    try:
        from django_q.models import Schedule
        
        # Cria ou atualiza o agendamento
        Schedule.objects.update_or_create(
            name="Bom Dia Operacional do Bot",
            defaults={
                "func": "apps.bot.tasks.send_daily_summary",
                "schedule_type": Schedule.DAILY,
                "repeats": -1
            }
        )
        logger.info("[Bot Tasks] Schedule do Bom Dia configurado com sucesso (Diário). Ajuste a hora no Painel.")
    except Exception as exc:
        logger.exception("[Bot Tasks] Erro ao configurar agenda do Bom Dia: %s", exc)
