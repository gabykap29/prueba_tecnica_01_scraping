import asyncio
import json
import random
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class DeliverySnapshot(BaseModel):
    platform: str
    address: str
    zone_type: str
    restaurant: str
    product_name: str
    product_price: Optional[float] = None
    delivery_fee: Optional[float] = None
    service_fee: Optional[float] = None
    estimated_time_min: Optional[int] = None
    active_promo: Optional[str] = None
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None

    @field_validator("product_price", "delivery_fee", "service_fee", mode="before")
    @classmethod
    def parse_price(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            return float(cleaned) if cleaned else None
        return float(v)


class BaseScraper(ABC):
    BASE_URL: str = ""
    PLATFORM_NAME: str = ""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    ]

    ADDRESSES = [
        {"address": "Presidente Masaryk 61, Polanco, CDMX", "zone": "high"},
        {"address": "Moliere 222, Polanco, CDMX", "zone": "high"},
        {"address": "Av. Santa Fe 495, Cuajimalpa, CDMX", "zone": "high"},
        {"address": "Av. Álvaro Obregón 110, Roma Norte, CDMX", "zone": "mid"},
        {"address": "Tamaulipas 66, Condesa, CDMX", "zone": "mid"},
        {"address": "Medellín 65, Roma Sur, CDMX", "zone": "mid"},
        {"address": "Av. Coyoacán 1035, Del Valle, CDMX", "zone": "mid"},
        {"address": "Eje Central 18, Centro Histórico, CDMX", "zone": "mid"},
        {"address": "Av. Tláhuac 3000, Iztapalapa, CDMX", "zone": "periphery"},
        {
            "address": "Av. Ermita Iztapalapa 1020, Iztapalapa, CDMX",
            "zone": "periphery",
        },
        {"address": "Av. Canal de Garay 50, Xochimilco, CDMX", "zone": "periphery"},
        {"address": "Av. Vallejo 880, Gustavo A. Madero, CDMX", "zone": "periphery"},
    ]

    TARGET_RESTAURANTS = ["McDonald's", "Burger King"]
    TARGET_PRODUCTS = ["Big Mac", "Whopper", "Combo Big Mac", "Combo Whopper"]

    def __init__(self, output_dir: str = "data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser = None
        self.context = None
        self.page = None

    async def create_stealth_context(self, playwright) -> tuple:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=random.choice(self.USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            extra_http_headers={
                "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return browser, context

    async def set_location(self, page: Page, address: str) -> bool:
        raise NotImplementedError("Subclass must implement set_location")

    async def scrape_restaurant(
        self,
        page: Page,
        restaurant_name: str,
        address_info: dict,
    ) -> list[DeliverySnapshot]:
        raise NotImplementedError("Subclass must implement scrape_restaurant")

    async def extract_text(self, page: Page, selectors: list[str]) -> Optional[str]:
        for selector in selectors:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    text = await el.text_content(timeout=3000)
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return None

    async def find_product_price(self, page: Page, product_name: str) -> Optional[str]:
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(1000)

            items = page.locator("[data-testid='rich-text'], [class*='MenuItem']")
            count = await items.count()

            for i in range(min(count, 50)):
                item = items.nth(i)
                text = await item.text_content(timeout=2000)
                if text and product_name.lower() in text.lower():
                    price_el = item.locator("span:has-text('$')").first
                    if await price_el.count() > 0:
                        return await price_el.text_content(timeout=2000)
        except Exception as e:
            logger.debug(f"find_product_price error para {product_name}: {e}")
        return None

    async def is_blocked(self, page: Page) -> bool:
        try:
            content = await page.content()
            blocked_signals = [
                "captcha",
                "robot",
                "access denied",
                "blocked",
                "verify you are human",
            ]
            return any(s in content.lower() for s in blocked_signals)
        except Exception:
            return False

    def parse_minutes(self, text: Optional[str]) -> Optional[int]:
        if not text:
            return None
        import re

        nums = re.findall(r"\d+", text)
        if not nums:
            return None
        values = [int(n) for n in nums]
        return sum(values) // len(values)

    async def run(self, output_file: Optional[str] = None) -> list[dict]:
        all_results = []
        if output_file is None:
            output_file = f"{self.PLATFORM_NAME}_raw.json"

        async with async_playwright() as p:
            self.browser, self.context = await self.create_stealth_context(p)
            self.page = await self.context.new_page()

            for addr_info in self.ADDRESSES:
                logger.info(
                    f"\n--- Procesando: {addr_info['address']} [{addr_info['zone']}] ---"
                )

                location_ok = await self.set_location(self.page, addr_info["address"])
                if not location_ok:
                    logger.warning(f"Saltando {addr_info['address']}")
                    continue

                for restaurant in self.TARGET_RESTAURANTS:
                    results = await self.scrape_restaurant(
                        self.page, restaurant, addr_info
                    )
                    all_results.extend([r.model_dump() for r in results])

                    delay = random.uniform(3.0, 6.0)
                    logger.info(f"Esperando {delay:.1f}s...")
                    await asyncio.sleep(delay)

                output_path = self.output_dir / output_file
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)

            await self.browser.close()

        logger.info(f"Scraping completado. {len(all_results)} registros")
        return all_results
