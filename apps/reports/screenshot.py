"""
DashboardScreenshotService
==========================
Gera um screenshot de alta qualidade do Dashboard Estratégico
usando Playwright (navegador headless Chromium).

Uso:
    service = DashboardScreenshotService()
    jpeg_bytes = service.generate(month=4, year=2026)
    # jpeg_bytes pode ser salvo em disco ou enviado via WhatsApp

Requisito:
    pip install playwright
    playwright install chromium
"""
from __future__ import annotations

import asyncio
from datetime import date

from django.conf import settings


class DashboardScreenshotService:
    # Largura da página em px (igual ao template dashboard_print.html)
    VIEWPORT_WIDTH = 1440
    VIEWPORT_HEIGHT = 900

    # Escala de pixel: 2 = dobra a resolução (ótimo para apresentações)
    DEVICE_SCALE_FACTOR = 2

    # Qualidade JPEG (1-100). 95 é excelente para apresentações.
    JPEG_QUALITY = 95

    # Tempo de espera (ms) para os gráficos Chart.js renderizarem
    CHART_RENDER_WAIT_MS = 1800

    def generate(self, month: int | None = None, year: int | None = None) -> bytes:
        """
        Gera o screenshot e retorna os bytes JPEG.

        Args:
            month: mês (1-12). None = mês atual.
            year:  ano (ex: 2026). None = ano atual.

        Returns:
            bytes: imagem JPEG pronta para salvar ou enviar.
        """
        today = date.today()
        month = month or today.month
        year = year or today.year
        return asyncio.run(self._capture(month, year))

    async def _capture(self, month: int, year: int) -> bytes:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright não está instalado. Execute:\n"
                "  .venv/bin/pip install playwright\n"
                "  .venv/bin/playwright install chromium"
            ) from exc

        token = settings.DASHBOARD_SCREENSHOT_TOKEN
        base_url = settings.DASHBOARD_SCREENSHOT_BASE_URL
        url = f"{base_url}/reports/print/?period={month}_{year}&token={token}"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": self.VIEWPORT_WIDTH, "height": self.VIEWPORT_HEIGHT},
                device_scale_factor=self.DEVICE_SCALE_FACTOR,
            )
            page = await context.new_page()

            # Abre a URL e aguarda a rede ficar ociosa (JS carregado)
            await page.goto(url, wait_until="networkidle", timeout=30_000)

            # Aguarda os gráficos renderizarem
            await page.wait_for_timeout(self.CHART_RENDER_WAIT_MS)

            # Tira o screenshot da página inteira
            screenshot_bytes = await page.screenshot(
                type="jpeg",
                quality=self.JPEG_QUALITY,
                full_page=True,
            )

            await browser.close()
            return screenshot_bytes
