from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProviderSendResult:
    success: bool
    message: str
    status_code: int | None = None
    response_payload: dict | None = None


class BaseNotificationProvider:
    def send_text(self, *, destination: str, text: str) -> ProviderSendResult:
        raise NotImplementedError

