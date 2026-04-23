from __future__ import annotations

from apps.core.models import OperationalSettings
from apps.passwords.services import OneTimeSecretClient
from apps.shared.repositories.passwords import PasswordLinkRepository
from apps.shared.repositories.people import ColaboradorRepository


class PasswordManagementService:
    def __init__(self):
        self.links = PasswordLinkRepository()
        self.collaborators = ColaboradorRepository()

    def recent_links(self, limit: int = 15):
        return self.links.recent(limit=limit)

    def search_collaborators(self, query: str, limit: int = 8):
        return self.collaborators.search(query, limit=limit)

    def create_link(self, *, collaborator_id: int, senha: str, descricao: str, ttl_seconds: int, username: str):
        collaborator = self.collaborators.get_by_id(collaborator_id)
        if not collaborator:
            raise ValueError("A pessoa selecionada não foi encontrada no banco.")

        settings = OperationalSettings.get_solo()
        if not settings.onetimesecret_enabled:
            raise ValueError("OneTimeSecret está desabilitado no admin.")

        if not settings.onetimesecret_email or not settings.onetimesecret_api_key:
            raise ValueError("Configure email e API key do OneTimeSecret no admin.")

        client = OneTimeSecretClient(
            email=settings.onetimesecret_email,
            api_key=settings.onetimesecret_api_key,
        )
        result = client.create_secret(secret=senha, ttl_seconds=ttl_seconds)
        if not result["success"]:
            raise ValueError(result["message"])

        return self.links.create(
            senha_usada=senha,
            secret_key=result["secret_key"],
            link_url=result["link_url"],
            ttl_seconds=result["ttl_seconds"],
            metadata_key=result["metadata_key"],
            nome_pessoa=collaborator.nome,
            gestor_pessoa=collaborator.gestor or "",
            descricao=descricao,
            finalidade="Acesso Temporário",
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
        result = client.check_status(password_link.metadata_key)
        if not result["success"]:
            raise ValueError(result["message"])
        if result["viewed"]:
            self.links.mark_viewed(password_link.pk)
        return password_link, result
