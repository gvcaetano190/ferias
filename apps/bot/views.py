"""
Webhook receptor de mensagens WhatsApp via Evolution API.

A Evolution API envia um POST neste endpoint quando uma mensagem chega.
Retornamos HTTP 200 imediatamente e processamos o comando.
"""
from __future__ import annotations

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _extract_message(data: dict) -> tuple[str, str]:
    """
    Extrai (reply_to, text) do payload da Evolution API.
    reply_to = JID completo para grupos, número para chats privados.
    Retorna ("", "") se não for uma mensagem de texto processável.
    """
    try:
        msg_data = data.get("data", {})
        key = msg_data.get("key", {})

        # Ignora mensagens enviadas pelo próprio bot (evita loop)
        if key.get("fromMe"):
            logger.debug("[Bot Webhook] Ignorando mensagem própria (fromMe=true)")
            return "", ""

        remote_jid = key.get("remoteJid", "")

        # Ignora status broadcasts (notificações de leitura, etc.)
        if "status@broadcast" in remote_jid:
            return "", ""

        # Para grupos (@g.us), mantém o JID completo para responder no grupo
        # Para chats privados (@s.whatsapp.net), extrai só o número
        if "@g.us" in remote_jid:
            reply_to = remote_jid
        elif "@" in remote_jid:
            reply_to = remote_jid.split("@")[0]
        else:
            reply_to = remote_jid

        # Tenta extrair o texto em diferentes formatos de mensagem
        message = msg_data.get("message", {})
        if not message or not isinstance(message, dict):
            return "", ""

        text = (
            message.get("conversation")
            or message.get("extendedTextMessage", {}).get("text")
            or ""
        )

        return reply_to, text.strip()
    except Exception as exc:
        logger.warning(f"[Bot Webhook] Erro ao extrair mensagem: {exc}")
        return "", ""


@csrf_exempt
@require_POST
def webhook(request):
    """
    Endpoint que a Evolution API chama quando uma mensagem WhatsApp chega.
    URL: POST /bot/webhook/
    """
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "ignored", "reason": "invalid_json"}, status=200)

    event = payload.get("event", "")

    # Log do evento recebido para debug
    logger.info(f"[Bot Webhook] Evento recebido: {event}")

    # Só processa mensagens recebidas
    if event not in ("messages.upsert", "message.received"):
        return JsonResponse({"status": "ignored", "reason": "event_not_handled"}, status=200)

    reply_to, text = _extract_message(payload)

    if not reply_to or not text:
        return JsonResponse({"status": "ignored", "reason": "no_text_or_sender"}, status=200)

    # Só responde no grupo autorizado
    from django.conf import settings
    allowed_group = getattr(settings, "BOT_ALLOWED_GROUP", "")
    if allowed_group and reply_to != allowed_group:
        logger.debug(f"[Bot Webhook] Ignorando mensagem fora do grupo autorizado: {reply_to}")
        return JsonResponse({"status": "ignored", "reason": "not_allowed_group"}, status=200)

    logger.info(f"[Bot Webhook] 📩 De={reply_to} | Texto={text!r}")

    # Processa o comando
    try:
        from apps.bot.services import BotService
        BotService().handle(sender=reply_to, text=text)
    except Exception as exc:
        logger.exception(f"[Bot Webhook] Erro ao processar comando: {exc}")

    return JsonResponse({"status": "ok"}, status=200)
