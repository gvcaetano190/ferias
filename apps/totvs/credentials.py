from __future__ import annotations

import json
from dataclasses import dataclass

try:
    import keyring
except ImportError:  # pragma: no cover
    keyring = None


KEYRING_SERVICE_NAME = "controle-ferias/totvs"


@dataclass
class TotvsCredential:
    username: str
    password: str


class TotvsCredentialStore:
    def __init__(self, service_name: str = KEYRING_SERVICE_NAME):
        self.service_name = service_name

    def save(self, *, credential_key: str, username: str, password: str) -> None:
        self._ensure_backend()
        payload = json.dumps(
            {
                "username": username,
                "password": password,
            },
            ensure_ascii=False,
        )
        keyring.set_password(self.service_name, credential_key, payload)

    def load(self, *, credential_key: str) -> TotvsCredential | None:
        self._ensure_backend()
        payload = keyring.get_password(self.service_name, credential_key)
        if not payload:
            return None
        data = json.loads(payload)
        return TotvsCredential(
            username=str(data.get("username") or ""),
            password=str(data.get("password") or ""),
        )

    def exists(self, *, credential_key: str) -> bool:
        return self.load(credential_key=credential_key) is not None

    def _ensure_backend(self) -> None:
        if keyring is None:
            raise RuntimeError(
                "Biblioteca 'keyring' nao instalada. Instale a dependencia para usar o cofre seguro."
            )

