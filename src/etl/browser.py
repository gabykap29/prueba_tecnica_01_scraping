"""Shared browser setup for live scrapers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "Chrome/143.0.0.0 Safari/537.36"
)


def scraper_user_agent() -> str:
    """Return a single modern UA so browser headers remain consistent."""
    return os.getenv("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT)


async def apply_stealth(page: Page) -> bool:
    """Apply playwright-stealth when the optional dependency is installed."""
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None

    if stealth_async is not None:
        await stealth_async(page)
        return True

    try:
        from playwright_stealth import Stealth
    except ImportError:
        return False

    stealth = Stealth(
        navigator_languages_override=("es-MX", "es"),
        navigator_platform_override="Win32",
        navigator_user_agent_override=scraper_user_agent(),
    )
    await stealth.apply_stealth_async(page)
    return True


async def create_stealth_page(
    playwright: Any,
    *,
    headless: bool,
    storage_state: str | None = None,
) -> tuple[Browser, BrowserContext, Page, bool]:
    """Create a Playwright page with consistent browser fingerprint settings."""
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-features=IsolateOrigins,site-per-process",
        ],
    )

    context_kwargs: dict[str, Any] = {
        "user_agent": scraper_user_agent(),
        "viewport": {"width": 1366, "height": 768},
        "locale": "es-MX",
        "timezone_id": "America/Mexico_City",
        "extra_http_headers": {
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Upgrade-Insecure-Requests": "1",
        },
    }
    if storage_state and Path(storage_state).exists():
        context_kwargs["storage_state"] = storage_state

    context = await browser.new_context(**context_kwargs)
    await context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['es-MX', 'es', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
    )
    page = await context.new_page()
    stealth_applied = await apply_stealth(page)
    return browser, context, page, stealth_applied
