from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.utils import OperationalError, ProgrammingError


class OperationalSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    company_name = models.CharField(max_length=120, default="Sistema de Controle de Férias")
    auto_start_scheduler_with_server = models.BooleanField(default=False)
    google_sheets_url = models.URLField(blank=True)
    sync_enabled = models.BooleanField(default=True)
    cache_minutes = models.PositiveIntegerField(default=60)
    onetimesecret_enabled = models.BooleanField(default=True)
    onetimesecret_email = models.EmailField(blank=True)
    onetimesecret_api_key = models.CharField(max_length=255, blank=True)
    allowed_systems = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração operacional"
        verbose_name_plural = "Configurações operacionais"

    def save(self, *args, **kwargs):
        self.pk = 1
        if not self.allowed_systems:
            self.allowed_systems = list(settings.DEFAULT_ACCESS_SYSTEMS)
        if not self.google_sheets_url:
            self.google_sheets_url = settings.GOOGLE_SHEETS_URL
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> "OperationalSettings":
        defaults = {
            "company_name": "Sistema de Controle de Férias",
            "google_sheets_url": settings.GOOGLE_SHEETS_URL,
            "sync_enabled": True,
            "cache_minutes": 60,
            "onetimesecret_enabled": True,
            "allowed_systems": list(settings.DEFAULT_ACCESS_SYSTEMS),
        }
        try:
            obj, _ = cls.objects.get_or_create(pk=1, defaults=defaults)
            return obj
        except (OperationalError, ProgrammingError):
            return cls(pk=1, **defaults)

    def __str__(self) -> str:
        return "Configuração principal"
