from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from apps.core.models import OperationalSettings
from apps.passwords.services import OneTimeSecretClient
from apps.shared.repositories.passwords import PasswordLinkRepository
from apps.shared.repositories.people import ColaboradorRepository


class PasswordManagementService:
    def __init__(self):
        self.links = PasswordLinkRepository()
        self.collaborators = ColaboradorRepository()

    def recent_links(self, limit: int = 15, query: str = ""):
        items = self.links.recent(limit=limit, query=query)
        for item in items:
            self.decorate_link(item)
        return items

    def decorate_link(self, item):
        now = timezone.now()
        expires_at = None

        # Em parte do legado, `expirado_em` já vinha salvo como a data-limite do link.
        if item.expirado_em and item.expirado_em > now:
            expires_at = item.expirado_em
        elif item.criado_em and item.ttl_seconds:
            expires_at = item.criado_em + timedelta(seconds=item.ttl_seconds)
        elif item.expirado_em:
            expires_at = item.expirado_em

        remaining_seconds = 0
        if expires_at:
            remaining_seconds = max(0, int((expires_at - now).total_seconds()))

        is_expired = bool(expires_at and expires_at <= now and not item.visualizado)

        item.ttl_label = self._format_duration(item.ttl_seconds or 0)
        item.expires_at = expires_at
        item.remaining_seconds = remaining_seconds
        item.remaining_label = "Expirado" if is_expired else self._format_duration(remaining_seconds)
        if item.visualizado:
            item.status_label = "Visualizado"
            item.status_style = "bg-emerald-100 text-emerald-700"
        elif is_expired:
            item.status_label = "Expirado"
            item.status_style = "bg-slate-200 text-slate-700"
        else:
            item.status_label = "Pendente"
            item.status_style = "bg-amber-100 text-amber-700"
        return item

    def search_collaborators(self, query: str, limit: int = 8):
        return self.collaborators.search(query, limit=limit)

    def create_link(
        self,
        *,
        secret_payload: str,
        descricao: str,
        ttl_seconds: int,
        username: str,
        nome_pessoa: str = "",
        gestor_pessoa: str = "",
        finalidade: str = "Acesso Temporário",
    ):
        settings = OperationalSettings.get_solo()
        if not settings.onetimesecret_enabled:
            raise ValueError("OneTimeSecret está desabilitado no admin.")

        if not settings.onetimesecret_email or not settings.onetimesecret_api_key:
            raise ValueError("Configure email e API key do OneTimeSecret no admin.")

        client = OneTimeSecretClient(
            email=settings.onetimesecret_email,
            api_key=settings.onetimesecret_api_key,
        )
        result = client.create_secret(secret=secret_payload, ttl_seconds=ttl_seconds)
        if not result["success"]:
            raise ValueError(result["message"])

        return self.links.create(
            senha_usada=secret_payload,
            secret_key=result["secret_key"],
            link_url=result["link_url"],
            ttl_seconds=result["ttl_seconds"],
            metadata_key=result["metadata_key"],
            nome_pessoa=nome_pessoa or "Segredo livre",
            gestor_pessoa=gestor_pessoa or "",
            descricao=descricao,
            finalidade=finalidade,
            usuario_criador=username,
        )

    def check_status(self, pk: int):
        password_link = self.links.get(pk)
        if not password_link:
            raise ValueError("Link de senha não encontrado.")
        if not password_link.metadata_key:
            raise ValueError("Esse link não possui metadata_key para consulta.")

        settings = OperationalSettings.get_solo()
        if not settings.onetimesecret_email or not settings.onetimesecret_api_key:
            raise ValueError("Configure email e API key do OneTimeSecret no admin.")

        client = OneTimeSecretClient(
            email=settings.onetimesecret_email,
            api_key=settings.onetimesecret_api_key,
        )
        result = client.check_status(password_link.metadata_key, password_link.link_url or "")
        if not result["success"]:
            raise ValueError(result["message"])
        if result["viewed"]:
            self.links.mark_viewed(password_link.pk)
        elif result["raw_state"] == "expired":
            self.links.mark_expired(password_link.pk)
        password_link = self.links.get(pk)
        return self.decorate_link(password_link), result

    def _format_duration(self, total_seconds: int) -> str:
        seconds = max(0, int(total_seconds))
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, secs = divmod(remainder, 60)

        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}min")
        if secs and not days and len(parts) < 2:
            parts.append(f"{secs}s")

        return " ".join(parts) if parts else "0s"
