from __future__ import annotations

from django.utils import timezone

from apps.notifications.models import (
    NotificationDelivery,
    NotificationDivergenceAudit,
    NotificationProviderConfig,
    NotificationTarget,
)
from apps.notifications.providers import EvolutionWhatsAppProvider


class NotificationService:
    TEST_EVENT_KEY = "notifications.test"
    DIVERGENCE_EVENT_KEY = "notifications.divergence.validated"
    TASK_EVENT_KEY = "notifications.task.status"

    def get_provider(self, config: NotificationProviderConfig):
        if config.provider_type == NotificationProviderConfig.TYPE_EVOLUTION:
            return EvolutionWhatsAppProvider(
                endpoint_url=config.endpoint_url,
                api_key=config.api_key,
                timeout_seconds=config.timeout_seconds,
            )
        raise ValueError(f"Provider nao suportado: {config.provider_type}")

    def send_text(
        self,
        *,
        provider_config: NotificationProviderConfig,
        target: NotificationTarget,
        text: str,
        event_key: str = "",
        dedupe_key: str = "",
    ) -> NotificationDelivery:
        delivery = NotificationDelivery.objects.create(
            event_key=event_key,
            dedupe_key=dedupe_key,
            provider=provider_config,
            target=target,
            destination_snapshot=target.destination,
            message_preview=text[:1000],
            status=NotificationDelivery.STATUS_PENDING,
        )

        provider = self.get_provider(provider_config)
        result = provider.send_text(destination=target.destination, text=text)

        delivery.provider_response = result.response_payload or {}
        if result.success:
            delivery.status = NotificationDelivery.STATUS_SENT
            delivery.sent_at = timezone.now()
            delivery.error_message = ""
        else:
            delivery.status = NotificationDelivery.STATUS_FAILED
            delivery.error_message = result.message
        delivery.save(update_fields=["provider_response", "status", "sent_at", "error_message"])
        return delivery

    def get_default_target(self, provider_config: NotificationProviderConfig | None = None) -> NotificationTarget | None:
        if provider_config and provider_config.default_target and provider_config.default_target.enabled:
            return provider_config.default_target

        global_default = (
            NotificationTarget.objects.filter(enabled=True, is_default=True)
            .order_by("-updated_at", "id")
            .first()
        )
        if global_default:
            return global_default

        enabled_targets = NotificationTarget.objects.filter(enabled=True).order_by("id")
        if enabled_targets.count() == 1:
            return enabled_targets.first()
        return None

    def send_test_message(
        self,
        *,
        provider_config: NotificationProviderConfig,
        text: str,
        target: NotificationTarget | None = None,
    ) -> NotificationDelivery:
        if not provider_config.enabled:
            raise ValueError("O provider de notificacao esta desabilitado.")

        target_obj = target or self.get_default_target(provider_config)
        if target_obj is None:
            raise ValueError("Nenhum destino de notificacao configurado para teste.")
        if not target_obj.enabled:
            raise ValueError("O destino selecionado para teste esta desabilitado.")

        return self.send_text(
            provider_config=provider_config,
            target=target_obj,
            text=text,
            event_key=self.TEST_EVENT_KEY,
        )

    def get_default_enabled_provider(self) -> NotificationProviderConfig | None:
        return (
            NotificationProviderConfig.objects.select_related("default_target")
            .filter(enabled=True)
            .order_by("-updated_at", "id")
            .first()
        )

    def notify_operational_divergence(
        self,
        *,
        collaborator_id: int,
        collaborator_name: str,
        usuario_ad: str,
        email: str,
        system_name: str,
        initial_action: str,
        sheet_status: str,
        real_status: str,
        internal_status_after_sync: str,
        vpn_sheet_status: str = "",
        vpn_real_status: str = "",
        vpn_internal_status_after_sync: str = "",
        vpn_changed: bool = False,
        data_saida=None,
        data_retorno=None,
        details: dict | None = None,
    ) -> tuple[NotificationDivergenceAudit, NotificationDelivery | None]:
        divergence_type = self._map_divergence_type(initial_action)
        dedupe_key = self._build_divergence_dedupe_key(
            usuario_ad=usuario_ad,
            email=email,
            system_name=system_name,
            divergence_type=divergence_type,
            data_saida=data_saida,
            data_retorno=data_retorno,
        )
        audit, created = NotificationDivergenceAudit.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "source_module": NotificationDivergenceAudit.SOURCE_BLOCK_OPERATIONAL,
                "divergence_type": divergence_type,
                "collaborator_id": collaborator_id,
                "collaborator_name": collaborator_name,
                "usuario_ad": usuario_ad or "",
                "email": email or "",
                "system_name": system_name,
                "initial_action": initial_action,
                "sheet_status": sheet_status or "",
                "real_status": real_status or "",
                "internal_status_after_sync": internal_status_after_sync or "",
                "data_saida": data_saida,
                "data_retorno": data_retorno,
                "details": details or {},
            },
        )
        if not created:
            audit.collaborator_name = collaborator_name
            audit.usuario_ad = usuario_ad or ""
            audit.email = email or ""
            audit.system_name = system_name
            audit.initial_action = initial_action
            audit.sheet_status = sheet_status or ""
            audit.real_status = real_status or ""
            audit.internal_status_after_sync = internal_status_after_sync or ""
            audit.data_saida = data_saida
            audit.data_retorno = data_retorno
            audit.details = details or {}
            audit.save(
                update_fields=[
                    "collaborator_name",
                    "usuario_ad",
                    "email",
                    "system_name",
                    "initial_action",
                    "sheet_status",
                    "real_status",
                    "internal_status_after_sync",
                    "data_saida",
                    "data_retorno",
                    "details",
                    "updated_at",
                ]
            )

        provider_config = self.get_default_enabled_provider()
        target = self.get_default_target(provider_config) if provider_config else None
        if provider_config is None or target is None:
            return audit, None

        if audit.notified_at:
            return audit, NotificationDelivery.objects.create(
                event_key=self.DIVERGENCE_EVENT_KEY,
                dedupe_key=dedupe_key,
                provider=provider_config,
                target=target,
                destination_snapshot=target.destination,
                message_preview=self._build_duplicate_message_preview(collaborator_name, system_name, real_status),
                status=NotificationDelivery.STATUS_SKIPPED,
                error_message="Divergencia ja notificada anteriormente.",
            )

        text = self._build_divergence_message(
            collaborator_name=collaborator_name,
            usuario_ad=usuario_ad,
            email=email,
            system_name=system_name,
            initial_action=initial_action,
            sheet_status=sheet_status,
            real_status=real_status,
            internal_status_after_sync=internal_status_after_sync,
            vpn_sheet_status=vpn_sheet_status,
            vpn_real_status=vpn_real_status,
            vpn_internal_status_after_sync=vpn_internal_status_after_sync,
            vpn_changed=vpn_changed,
            data_saida=data_saida,
            data_retorno=data_retorno,
        )
        delivery = self.send_text(
            provider_config=provider_config,
            target=target,
            text=text,
            event_key=self.DIVERGENCE_EVENT_KEY,
            dedupe_key=dedupe_key,
        )
        if delivery.status == NotificationDelivery.STATUS_SENT:
            audit.notified_at = timezone.now()
            audit.save(update_fields=["notified_at", "updated_at"])
        return audit, delivery

    def notify_task_status(
        self,
        *,
        task_key: str,
        task_label: str,
        status: str,
        summary: str,
        details: list[str] | None = None,
    ) -> NotificationDelivery | None:
        provider_config = self.get_default_enabled_provider()
        target = self.get_default_target(provider_config) if provider_config else None
        if provider_config is None or target is None:
            return None

        text = self._build_task_status_message(
            task_label=task_label,
            status=status,
            summary=summary,
            details=details or [],
        )
        return self.send_text(
            provider_config=provider_config,
            target=target,
            text=text,
            event_key=self.TASK_EVENT_KEY,
            dedupe_key=f"{task_key}|{timezone.now().isoformat()}",
        )

    def _map_divergence_type(self, initial_action: str) -> str:
        if initial_action == "BLOQUEAR":
            return NotificationDivergenceAudit.TYPE_BLOCK_ALREADY_BLOCKED
        return NotificationDivergenceAudit.TYPE_UNBLOCK_ALREADY_RELEASED

    def _build_divergence_dedupe_key(
        self,
        *,
        usuario_ad: str,
        email: str,
        system_name: str,
        divergence_type: str,
        data_saida,
        data_retorno,
    ) -> str:
        identity = (usuario_ad or email or "sem-identidade").strip().lower()
        return "|".join(
            [
                identity,
                system_name.strip().upper(),
                divergence_type,
                data_saida.isoformat() if data_saida else "-",
                data_retorno.isoformat() if data_retorno else "-",
            ]
        )

    def _build_duplicate_message_preview(self, collaborator_name: str, system_name: str, real_status: str) -> str:
        return (
            f"Divergencia ja notificada para {collaborator_name} em {system_name}. "
            f"Status real confirmado: {real_status or '-'}."
        )

    def _build_divergence_message(
        self,
        *,
        collaborator_name: str,
        usuario_ad: str,
        email: str,
        system_name: str,
        initial_action: str,
        sheet_status: str,
        real_status: str,
        internal_status_after_sync: str,
        vpn_sheet_status: str,
        vpn_real_status: str,
        vpn_internal_status_after_sync: str,
        vpn_changed: bool,
        data_saida,
        data_retorno,
    ) -> str:
        acao_humana = "bloqueio" if initial_action == "BLOQUEAR" else "desbloqueio"
        lines = [
            "⚠️ Divergencia detectada entre planilha e Active Directory.",
            f"Usuario: {collaborator_name}",
            f"Login AD: {usuario_ad or '-'}",
            f"Email: {email or '-'}",
            f"Sistema: {system_name}",
            f"Planilha pedia: {acao_humana} ({sheet_status or '-'})",
            f"Status real no AD: {real_status or '-'}",
            f"Status interno sincronizado para: {internal_status_after_sync or '-'}",
        ]
        if vpn_changed:
            lines.extend(
                [
                    "VPN:",
                    f"VPN na planilha/banco: {vpn_sheet_status or '-'}",
                    f"VPN real pelo grupo Printi_Acesso: {vpn_real_status or '-'}",
                    f"Status interno da VPN sincronizado para: {vpn_internal_status_after_sync or '-'}",
                ]
            )
        lines.extend(
            [
                f"Saida: {data_saida.strftime('%d/%m/%Y') if data_saida else '-'}",
                f"Retorno: {data_retorno.strftime('%d/%m/%Y') if data_retorno else '-'}",
                "Favor ajustar a planilha para refletir a realidade operacional.",
            ]
        )
        return "\n".join(lines)

    def _build_task_status_message(
        self,
        *,
        task_label: str,
        status: str,
        summary: str,
        details: list[str],
    ) -> str:
        lines = [
            f"📡 Tarefa finalizada: {task_label}",
            f"Status: {status.upper()}",
            f"Resumo: {summary}",
        ]
        lines.extend(detail for detail in details if detail)
        return "\n".join(lines)
