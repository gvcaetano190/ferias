from __future__ import annotations

from typing import Any

import requests


class TotvsClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, detail: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class TotvsClient:
    USERS_PATH = "/rest/api/framework/v1/users"

    def __init__(
        self,
        *,
        base_url: str,
        tenant_id: str,
        username: str,
        password: str,
        timeout_seconds: int = 30,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id.strip()
        self.username = username
        self.password = password
        self.timeout_seconds = int(timeout_seconds or 30)
        self.verify_ssl = bool(verify_ssl)
        self.session = requests.Session()

    def get_user(self, identifier: str) -> dict[str, Any]:
        return self._request("GET", f"{self.USERS_PATH}/{identifier}")

    def update_user_active(
        self,
        *,
        user_id: str,
        active: bool,
        current_payload: dict[str, Any] | None = None,
        fallback_email: str = "",
    ) -> dict[str, Any]:
        payload = current_payload or self.get_user(user_id)
        body = self._build_update_payload(payload, active=active, fallback_email=fallback_email)
        return self._request("PUT", f"{self.USERS_PATH}/{user_id}", json=body)

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "TenantId": self.tenant_id,
            "Accept": "application/json",
        }
        if method.upper() in {"POST", "PUT", "PATCH"}:
            headers["Content-Type"] = "application/json"
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                timeout=self.timeout_seconds,
                headers=headers,
                auth=(self.username, self.password),
                verify=self.verify_ssl,
                **kwargs,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            detail = self._extract_error_detail(exc.response)
            raise TotvsClientError(
                f"Erro HTTP {getattr(exc.response, 'status_code', '?')} ao chamar TOTVS: {detail}",
                status_code=getattr(exc.response, "status_code", None),
                detail=detail,
            ) from exc
        except requests.RequestException as exc:
            raise TotvsClientError(f"Falha de comunicacao com o TOTVS: {exc}") from exc

        try:
            return response.json()
        except ValueError as exc:
            raise TotvsClientError("TOTVS retornou uma resposta que nao e JSON valido.") from exc

    def _build_update_payload(self, payload: dict[str, Any], *, active: bool, fallback_email: str = "") -> dict[str, Any]:
        emails = payload.get("emails") or []
        normalized_emails = []
        primary_email_present = False
        for item in emails:
            email_item = dict(item)
            value = (email_item.get("value") or "").strip()
            if email_item.get("primary") and value:
                primary_email_present = True
            email_item["value"] = value
            normalized_emails.append(email_item)

        fallback_email = (fallback_email or "").strip()
        if not primary_email_present and fallback_email:
            if normalized_emails:
                normalized_emails[0]["value"] = fallback_email
                normalized_emails[0]["type"] = normalized_emails[0].get("type") or "work"
                normalized_emails[0]["primary"] = True
            else:
                normalized_emails = [
                    {
                        "value": fallback_email,
                        "type": "work",
                        "primary": True,
                    }
                ]

        body = {
            "schemas": payload.get("schemas")
            or [
                "urn:scim:schemas:core:2.0:User",
                "urn:scim:schemas:extension:enterprise:2.0:User",
            ],
            "id": str(payload.get("id") or ""),
            "userName": payload.get("userName") or "",
            "name": payload.get("name")
            or {
                "formatted": payload.get("displayName") or payload.get("userName") or "",
                "givenName": payload.get("userName") or "",
                "familyName": ".",
            },
            "emails": normalized_emails,
            "active": bool(active),
        }
        return body

    def _extract_error_detail(self, response: requests.Response | None) -> str:
        if response is None:
            return "Sem resposta do servidor."
        try:
            data = response.json()
        except ValueError:
            return response.text or "Sem detalhe retornado."
        if isinstance(data, dict):
            return str(data.get("message") or data.get("detail") or data.get("error") or data)
        return str(data)
