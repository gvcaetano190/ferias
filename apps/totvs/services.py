from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from django.utils import timezone

from apps.people.models import Acesso, Colaborador
from apps.shared.repositories.people import AcessoRepository
from apps.totvs.credentials import TotvsCredentialStore
from apps.totvs.models import TotvsIntegrationConfig
from integrations.totvs.client import TotvsClient, TotvsClientError


@dataclass
class TotvsResolvedUser:
    identifier: str
    user_id: str
    username: str
    active: bool
    status: str
    payload: dict
    found: bool = True


class TotvsIntegrationService:
    SYSTEM_NAME = "TOTVS"
    LOOKUP_MAX_WORKERS = 4

    def __init__(self):
        self.credential_store = TotvsCredentialStore()
        self.access_repository = AcessoRepository()

    def get_active_config(self) -> TotvsIntegrationConfig:
        config = TotvsIntegrationConfig.objects.filter(active=True).order_by("-updated_at").first()
        if not config:
            raise TotvsClientError("Nenhuma configuracao TOTVS ativa encontrada no admin.")
        return config

    def get_client(self, config: TotvsIntegrationConfig | None = None) -> TotvsClient:
        config = config or self.get_active_config()
        credentials = self.credential_store.load(credential_key=config.credential_key)
        if not credentials or not credentials.username or not credentials.password:
            raise TotvsClientError(
                "Credencial TOTVS nao encontrada no cofre. Regrave usuario e senha no admin."
            )
        return TotvsClient(
            base_url=config.base_url,
            tenant_id=config.tenant_id,
            username=credentials.username,
            password=credentials.password,
            timeout_seconds=config.timeout_seconds,
            verify_ssl=config.verify_ssl,
        )

    def consultar_usuario(self, identifier: str, *, config: TotvsIntegrationConfig | None = None) -> TotvsResolvedUser:
        config = config or self.get_active_config()
        client = self.get_client(config)
        try:
            payload = client.get_user(identifier)
        except TotvsClientError as exc:
            self._mark_test_result(
                config,
                status=TotvsIntegrationConfig.TEST_STATUS_ERROR,
                message=str(exc),
            )
            raise
        resolved = TotvsResolvedUser(
            identifier=identifier,
            user_id=str(payload.get("id") or ""),
            username=str(payload.get("userName") or identifier),
            active=bool(payload.get("active")),
            status="LIBERADO" if bool(payload.get("active")) else "BLOQUEADO",
            payload=payload,
            found=True,
        )
        self._mark_test_result(
            config,
            status=TotvsIntegrationConfig.TEST_STATUS_SUCCESS,
            message=f"Consulta GET realizada com sucesso para '{identifier}'.",
        )
        return resolved

    def atualizar_status_usuario(
        self,
        *,
        identifier: str,
        active: bool,
        config: TotvsIntegrationConfig | None = None,
    ) -> TotvsResolvedUser:
        config = config or self.get_active_config()
        client = self.get_client(config)
        collaborator = self._find_collaborator_for_identifier(identifier)
        try:
            current = client.get_user(identifier)
            user_id = str(current.get("id") or identifier)
            updated_payload = client.update_user_active(
                user_id=user_id,
                active=active,
                current_payload=current,
                fallback_email=getattr(collaborator, "email", "") or "",
            )
        except TotvsClientError as exc:
            self._mark_test_result(
                config,
                status=TotvsIntegrationConfig.TEST_STATUS_ERROR,
                message=str(exc),
            )
            raise
        resolved = TotvsResolvedUser(
            identifier=identifier,
            user_id=str(updated_payload.get("id") or user_id),
            username=str(updated_payload.get("userName") or current.get("userName") or identifier),
            active=bool(updated_payload.get("active")),
            status="LIBERADO" if bool(updated_payload.get("active")) else "BLOQUEADO",
            payload=updated_payload,
            found=True,
        )
        self._mark_test_result(
            config,
            status=TotvsIntegrationConfig.TEST_STATUS_SUCCESS,
            message=(
                f"PUT realizado com sucesso para '{resolved.username}' "
                f"com active={'true' if active else 'false'}."
            ),
        )
        return resolved

    def mark_error(self, *, message: str, config: TotvsIntegrationConfig | None = None) -> None:
        config = config or self.get_active_config()
        self._mark_test_result(
            config,
            status=TotvsIntegrationConfig.TEST_STATUS_ERROR,
            message=message,
        )

    def sincronizar_status_no_banco_por_login(
        self,
        *,
        login_ad: str,
    ) -> TotvsResolvedUser:
        normalized_login = (login_ad or "").strip().lower()
        if not normalized_login:
            raise TotvsClientError("Login do colaborador nao informado para sincronizar status TOTVS.")

        collaborator = Colaborador.objects.filter(login_ad__iexact=normalized_login).first()
        if not collaborator:
            raise TotvsClientError(f"Nenhum colaborador encontrado no banco com login_ad '{normalized_login}'.")

        try:
            resolved = self.consultar_usuario(normalized_login)
        except TotvsClientError as exc:
            if exc.status_code == 404:
                self.access_repository.upsert(
                    colaborador_id=collaborator.id,
                    sistema=self.SYSTEM_NAME,
                    status="NP",
                )
                return TotvsResolvedUser(
                    identifier=normalized_login,
                    user_id="",
                    username=normalized_login,
                    active=False,
                    status="NP",
                    payload={},
                    found=False,
                )
            raise

        self.access_repository.upsert(
            colaborador_id=collaborator.id,
            sistema=self.SYSTEM_NAME,
            status=resolved.status,
        )
        return resolved

    def consultar_usuarios_operacionais(self, identifiers: list[str]) -> list[dict]:
        normalized = []
        seen = set()
        for item in identifiers:
            key = (item or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            normalized.append(key)

        if not normalized:
            return []

        results: list[dict] = []
        with ThreadPoolExecutor(max_workers=self.LOOKUP_MAX_WORKERS) as executor:
            futures = {
                executor.submit(self._consultar_usuario_operacional, identifier): identifier
                for identifier in normalized
            }
            for future in as_completed(futures):
                results.append(future.result())
        return results

    def bloquear_usuarios_operacionais(self, identifiers: list[str]) -> list[dict]:
        return [self._alterar_usuario_operacional(identifier, active=False) for identifier in identifiers if identifier]

    def desbloquear_usuarios_operacionais(self, identifiers: list[str]) -> list[dict]:
        return [self._alterar_usuario_operacional(identifier, active=True) for identifier in identifiers if identifier]

    def _mark_test_result(self, config: TotvsIntegrationConfig, *, status: str, message: str) -> None:
        config.last_tested_at = timezone.now()
        config.last_test_status = status
        config.last_test_message = message
        config.save(update_fields=["last_tested_at", "last_test_status", "last_test_message", "updated_at"])

    def _consultar_usuario_operacional(self, identifier: str) -> dict:
        try:
            resolved = self.consultar_usuario(identifier)
            return {
                "success": True,
                "usuario_ad": identifier,
                "totvs_user_id": resolved.user_id,
                "totvs_status": resolved.status,
                "message": "Consulta TOTVS realizada com sucesso.",
                "user_found": True,
                "active": resolved.active,
            }
        except TotvsClientError as exc:
            if exc.status_code == 404:
                return {
                    "success": True,
                    "usuario_ad": identifier,
                    "totvs_user_id": "",
                    "totvs_status": "NP",
                    "message": "Usuario nao encontrado no TOTVS; status NP mantido.",
                    "user_found": False,
                    "active": False,
                }
            return {
                "success": False,
                "usuario_ad": identifier,
                "totvs_user_id": "",
                "totvs_status": "ERRO",
                "message": str(exc),
                "user_found": False,
                "active": False,
            }

    def _alterar_usuario_operacional(self, identifier: str, *, active: bool) -> dict:
        try:
            resolved = self.atualizar_status_usuario(identifier=identifier, active=active)
            return {
                "success": True,
                "usuario_ad": identifier,
                "totvs_user_id": resolved.user_id,
                "totvs_status": resolved.status,
                "message": "Atualizacao TOTVS realizada com sucesso.",
                "user_found": True,
                "active": resolved.active,
            }
        except TotvsClientError as exc:
            if exc.status_code == 404:
                return {
                    "success": True,
                    "usuario_ad": identifier,
                    "totvs_user_id": "",
                    "totvs_status": "NP",
                    "message": "Usuario nao encontrado no TOTVS; status NP mantido.",
                    "user_found": False,
                    "active": False,
                }
            return {
                "success": False,
                "usuario_ad": identifier,
                "totvs_user_id": "",
                "totvs_status": "ERRO",
                "message": str(exc),
                "user_found": False,
                "active": False,
            }

    def _find_collaborator_for_identifier(self, identifier: str) -> Colaborador | None:
        normalized = (identifier or "").strip()
        if not normalized:
            return None
        return (
            Colaborador.objects.filter(login_ad__iexact=normalized).first()
            or Colaborador.objects.filter(email__iexact=normalized).first()
        )
