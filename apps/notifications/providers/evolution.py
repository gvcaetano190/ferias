from __future__ import annotations

import base64

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

    def _base_url(self) -> str:
        """Extrai a URL base da Evolution API a partir do endpoint de sendText."""
        # endpoint_url é algo como: http://host:8081/message/sendText/instancia
        # queremos:                  http://host:8081
        parts = self.endpoint_url.split("/message/")
        return parts[0] if len(parts) > 1 else self.endpoint_url

    def _instance_name(self) -> str:
        """Extrai o nome da instância a partir do endpoint de sendText."""
        # endpoint_url: http://host:8081/message/sendText/instancia
        parts = self.endpoint_url.rsplit("/", 1)
        return parts[-1] if len(parts) > 1 else ""

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["apikey"] = self.api_key
        return h

    def send_text(self, *, destination: str, text: str) -> ProviderSendResult:
        if requests is None:
            return ProviderSendResult(success=False, message="Biblioteca requests nao disponivel.")
        if not self.endpoint_url:
            return ProviderSendResult(success=False, message="Endpoint da Evolution API nao configurado.")

        destination_value = self.format_destination(destination)
        if not destination_value:
            return ProviderSendResult(success=False, message="Destino de notificacao nao configurado.")

        payload = {
            "number": destination_value,
            "text": text,
        }
        try:
            response = requests.post(
                self.endpoint_url,
                json=payload,
                headers=self._headers(),
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

    def send_image(self, *, destination: str, image_bytes: bytes, caption: str = "") -> ProviderSendResult:
        """
        Envia uma imagem JPEG/PNG via Evolution API (sendMedia).

        Args:
            destination: número ou JID do destinatário.
            image_bytes: bytes da imagem (JPEG ou PNG).
            caption: legenda opcional exibida abaixo da imagem.
        """
        if requests is None:
            return ProviderSendResult(success=False, message="Biblioteca requests nao disponivel.")
        if not self.endpoint_url:
            return ProviderSendResult(success=False, message="Endpoint da Evolution API nao configurado.")

        destination_value = self.format_destination(destination)
        if not destination_value:
            return ProviderSendResult(success=False, message="Destino de notificacao nao configurado.")

        # Monta a URL de sendMedia a partir do endpoint de sendText
        base = self._base_url()
        instance = self._instance_name()
        media_url = f"{base}/message/sendMedia/{instance}"

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        payload = {
            "number": destination_value,
            "mediatype": "image",
            "mimetype": "image/jpeg",
            "caption": caption,
            "media": b64,
            "fileName": "dashboard.jpg",
        }

        try:
            response = requests.post(
                media_url,
                json=payload,
                headers=self._headers(),
                timeout=max(self.timeout_seconds, 60),  # imagens podem demorar mais
            )
        except requests.exceptions.Timeout:
            return ProviderSendResult(success=False, message="Timeout ao enviar imagem para Evolution API.")
        except requests.exceptions.ConnectionError:
            return ProviderSendResult(success=False, message="Falha de conexao com Evolution API.")
        except Exception as exc:
            return ProviderSendResult(success=False, message=f"Erro inesperado ao enviar imagem: {exc}")

        response_payload = None
        try:
            response_payload = response.json()
        except Exception:
            response_payload = {"raw": response.text}

        if response.status_code in {200, 201}:
            return ProviderSendResult(
                success=True,
                message="Imagem enviada com sucesso.",
                status_code=response.status_code,
                response_payload=response_payload,
            )

        return ProviderSendResult(
            success=False,
            message=f"Erro HTTP {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_payload=response_payload,
        )

    def send_buttons(self, *, destination: str, text: str, buttons: list[dict], footer: str = "") -> ProviderSendResult:
        """
        Envia uma mensagem com botões interativos via Evolution API (sendButtons).
        buttons: lista de dicionários no formato [{"id": "btn1", "text": "Texto do Botão"}]
        """
        if requests is None:
            return ProviderSendResult(success=False, message="Biblioteca requests nao disponivel.")
        if not self.endpoint_url:
            return ProviderSendResult(success=False, message="Endpoint da Evolution API nao configurado.")

        destination_value = self.format_destination(destination)
        if not destination_value:
            return ProviderSendResult(success=False, message="Destino de notificacao nao configurado.")

        base = self._base_url()
        instance = self._instance_name()
        buttons_url = f"{base}/message/sendButtons/{instance}"

        formatted_buttons = []
        for btn in buttons:
            formatted_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn.get("id", ""),
                    "title": btn.get("text", "")
                }
            })

        payload = {
            "number": destination_value,
            "options": {"delay": 1200},
            "buttonMessage": {
                "text": text,
                "footer": footer,
                "buttons": formatted_buttons
            }
        }

        try:
            response = requests.post(
                buttons_url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except requests.exceptions.Timeout:
            return ProviderSendResult(success=False, message="Timeout ao enviar botoes para Evolution API.")
        except requests.exceptions.ConnectionError:
            return ProviderSendResult(success=False, message="Falha de conexao com Evolution API.")
        except Exception as exc:
            return ProviderSendResult(success=False, message=f"Erro inesperado ao enviar botoes: {exc}")

        response_payload = None
        try:
            response_payload = response.json()
        except Exception:
            response_payload = {"raw": response.text}

        if response.status_code in {200, 201}:
            return ProviderSendResult(
                success=True,
                message="Botoes enviados com sucesso.",
                status_code=response.status_code,
                response_payload=response_payload,
            )

        return ProviderSendResult(
            success=False,
            message=f"Erro HTTP {response.status_code}: {response.text}",
            status_code=response.status_code,
            response_payload=response_payload,
        )
