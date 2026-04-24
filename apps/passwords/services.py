from __future__ import annotations

from typing import Any

import requests
from requests.auth import HTTPBasicAuth


class OneTimeSecretClient:
    BASE_URL = "https://eu.onetimesecret.com/api/v1"
    STATUS_BASE_URL = "https://eu.onetimesecret.com/api/v2"
    SECRET_URL_PREFIX = "https://eu.onetimesecret.com/secret/"
    GLOBAL_STATUS_BASE_URL = "https://onetimesecret.com/api/v2"
    EU_STATUS_BASE_URL = "https://eu.onetimesecret.com/api/v2"

    def __init__(self, email: str, api_key: str):
        self.auth = HTTPBasicAuth(email, api_key)

    def create_secret(self, secret: str, ttl_seconds: int) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self.BASE_URL}/share",
                auth=self.auth,
                data={"secret": secret, "ttl": ttl_seconds},
                timeout=30,
            )
        except requests.RequestException as exc:
            return {"success": False, "message": str(exc)}
        if response.status_code != 200:
            return {
                "success": False,
                "message": f"Erro HTTP {response.status_code}: {response.text}",
            }

        data = response.json()
        secret_key = data.get("secret_key", "")
        return {
            "success": True,
            "secret_key": secret_key,
            "metadata_key": data.get("metadata_key", ""),
            "link_url": f"{self.SECRET_URL_PREFIX}{secret_key}",
            "ttl_seconds": ttl_seconds,
        }

    def check_status(self, metadata_key: str, link_url: str = "") -> dict[str, Any]:
        status_base_url = self.EU_STATUS_BASE_URL if "eu.onetimesecret.com" in (link_url or "") else self.GLOBAL_STATUS_BASE_URL
        try:
            response = requests.get(
                f"{status_base_url}/private/{metadata_key}",
                auth=self.auth,
                timeout=30,
            )
        except requests.RequestException as exc:
            return {"success": False, "message": str(exc)}
        if response.status_code != 200:
            return {
                "success": False,
                "message": f"Erro HTTP {response.status_code}: {response.text}",
            }

        payload = response.json()
        record = payload.get("record", payload)
        received = record.get("received")
        state = record.get("state", "unknown")
        has_received_date = False
        if received:
            received_text = str(received).strip().lower()
            has_received_date = received_text not in {"", "none", "null"} and any(char.isdigit() for char in received_text)

        if state == "new":
            final_state = "new"
        elif state in {"received", "viewed"}:
            # Mantemos a regra do sistema antigo: sem data válida, ainda não marcamos como visualizado.
            final_state = "viewed" if has_received_date else "new"
        else:
            final_state = state

        return {
            "success": True,
            "viewed": final_state == "viewed",
            "viewed_at": received if has_received_date else None,
            "raw_state": final_state,
            "original_state": state,
        }
