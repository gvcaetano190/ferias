from __future__ import annotations

from apps.notifications.providers.base import BaseNotificationProvider, ProviderSendResult

try:
    import requests
except ImportError:  # pragma: no cover - protected by requirements
    requests = None


class EvolutionWhatsAppProvider(BaseNotificationProvider):
    def __init__(self, *, endpoint_url: str, api_key: str = "", timeout_seconds: int = 30) -> None:
        self.endpoint_url = (endpoint_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = max(int(timeout_seconds or 30), 1)

    def format_destination(self, raw_destination: str) -> str:
        value = (raw_destination or "").strip()
        if not value:
            return ""
        if "@" in value:
            return value
        digits = "".join(char for char in value if char.isdigit())
        if not digits.startswith("55") and len(digits) >= 10:
            digits = f"55{digits}"
        return digits

    def send_text(self, *, destination: str, text: str) -> ProviderSendResult:
        if requests is None:
            return ProviderSendResult(success=False, message="Biblioteca requests nao disponivel.")
        if not self.endpoint_url:
            return ProviderSendResult(success=False, message="Endpoint da Evolution API nao configurado.")

        destination_value = self.format_destination(destination)
        if not destination_value:
            return ProviderSendResult(success=False, message="Destino de notificacao nao configurado.")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["apikey"] = self.api_key

        payload = {
            "number": destination_value,
            "text": text,
        }
        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout:
            return ProviderSendResult(success=False, message="Timeout ao enviar mensagem para Evolution API.")
        except requests.exceptions.ConnectionError:
            return ProviderSendResult(success=False, message="Falha de conexao com Evolution API.")
        except Exception as exc:  # pragma: no cover - safeguard
            return ProviderSendResult(success=False, message=f"Erro inesperado ao enviar mensagem: {exc}")

        response_payload = None
        try:
            response_payload = response.json()
        except Exception:
            response_payload = {"raw": response.text}

        if response.status_code in {200, 201}:
            return ProviderSendResult(
                success=True,
                message="Mensagem enviada com sucesso.",
                status_code=response.status_code,
                response_payload=response_payload,
            )

        return ProviderSendResult(
            success=False,
            message=f"Erro HTTP {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_payload=response_payload,
        )

