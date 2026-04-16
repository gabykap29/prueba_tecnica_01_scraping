"""Base scraper functionality for the Rappi Analytics ETL pipeline.

This module provides the abstract base class for platform-specific scrapers,
including common functionality like browser setup, location handling,
and data extraction utilities.
"""

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, BrowserContext, Browser

from src.shared.config import get_settings
from src.shared.constants import (
    PlatformConstants,
    ZoneConstants,
    RestaurantConstants,
    ScrapingConstants,
)
from src.shared.exceptions import ScraperException, ScraperLocationException
from src.shared.utils import parse_price, parse_minutes
from src.etl.models import DeliverySnapshot

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for platform-specific web scrapers.

    This class provides common functionality for web scraping including:
    - Browser and context setup with stealth configuration
    - Location setting for delivery addresses
    - Restaurant and product data extraction
    - Rate limiting and error handling

    Subclasses must implement platform-specific methods.

    Attributes:
        BASE_URL: Base URL for the platform
        PLATFORM_NAME: Name identifier for the platform
    """

    BASE_URL: str = ""
    PLATFORM_NAME: str = ""

    def __init__(self, output_dir: str = "data"):
        """Initialize the scraper.

        Args:
            output_dir: Directory for output JSON files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.settings = get_settings()

    async def create_stealth_context(
        self,
        playwright,
    ) -> tuple[Browser, BrowserContext]:
        """Create a stealth browser context to avoid detection.

        Args:
            playwright: Playwright instance

        Returns:
            Tuple of (browser, context)
        """
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        user_agents = self.settings.USER_AGENTS
        context = await browser.new_context(
            user_agent=random.choice(user_agents),
            viewport={"width": 1366, "height": 768},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            extra_http_headers={
                "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
                "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"),
            },
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return browser, context

    async def set_location(self, page: Page, address: str) -> bool:
        """Set delivery location on the platform.

        Args:
            page: Playwright page instance
            address: Delivery address

        Returns:
            True if location was set successfully

        Raises:
            ScraperLocationException: If location setting fails
        """
        try:
            await page.goto(
                self.BASE_URL,
                wait_until="domcontentloaded",
                timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT,
            )
            await page.wait_for_timeout(random.randint(1500, 2500))

            address_input = page.locator(
                "[data-testid='address-input'], "
                "input[placeholder*='direccion'], "
                "input[placeholder*='address']"
            ).first
            await address_input.click()
            await page.wait_for_timeout(500)
            await address_input.fill(address)
            await page.wait_for_timeout(1500)

            suggestion = page.locator("[data-testid='address-suggestion']").first
            await suggestion.wait_for(timeout=ScrapingConstants.SELECTOR_TIMEOUT)
            await suggestion.click()
            await page.wait_for_timeout(2000)

            logger.info(f"Location set: {address}")
            return True

        except Exception as e:
            logger.warning(f"Failed to set location {address}: {e}")
            raise ScraperLocationException(
                f"Failed to set location: {address}", details={"address": address, "error": str(e)}
            )

    async def extract_text(self, page: Page, selectors: list[str]) -> Optional[str]:
        """Extract text using multiple selector fallback.

        Args:
            page: Playwright page instance
            selectors: List of CSS selectors to try

        Returns:
            Extracted text or None if not found
        """
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content(timeout=3000)
                    if text and text.strip():
                        return text.strip()
            except Exception:
                continue
        return None

    async def find_product_price(
        self,
        page: Page,
        product_name: str,
    ) -> Optional[str]:
        """Find product price by name search.

        Args:
            page: Playwright page instance
            product_name: Product name to search for

        Returns:
            Price text or None if not found
        """
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(1000)

            items = page.locator("[data-testid='rich-text'], [class*='MenuItem']")
            count = await items.count()

            for i in range(min(count, 50)):
                item = items.nth(i)
                text = await item.text_content(timeout=2000)
                if text and product_name.lower() in text.lower():
                    price_element = item.locator("span:has-text('$')").first
                    if await price_element.count() > 0:
                        return await price_element.text_content(timeout=2000)

        except Exception as e:
            logger.debug(f"Price search failed for {product_name}: {e}")

        return None

    async def is_blocked(self, page: Page) -> bool:
        """Check if page shows blocking signals.

        Args:
            page: Playwright page instance

        Returns:
            True if blocked detected
        """
        try:
            content = await page.content()
            blocked_signals = ScrapingConstants.BLOCKED_SIGNALS
            return any(signal in content.lower() for signal in blocked_signals)
        except Exception:
            return False

    async def scrape_restaurant(
        self,
        page: Page,
        restaurant_name: str,
        address_info: dict,
    ) -> list[DeliverySnapshot]:
        """Scrape restaurant data from the platform.

        This method must be implemented by subclasses with
        platform-specific logic.

        Args:
            page: Playwright page instance
            restaurant_name: Restaurant name to search for
            address_info: Address information dict

        Returns:
            List of delivery snapshots

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        raise NotImplementedError("Subclass must implement scrape_restaurant")

    @abstractmethod
    async def search_restaurant(
        self,
        page: Page,
        restaurant_name: str,
    ) -> bool:
        """Search for a restaurant on the platform.

        Args:
            page: Playwright page instance
            restaurant_name: Restaurant name

        Returns:
            True if search successful

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass

    @abstractmethod
    async def extract_product_data(
        self,
        page: Page,
        restaurant_name: str,
        address_info: dict,
    ) -> list[DeliverySnapshot]:
        """Extract product data from restaurant page.

        Args:
            page: Playwright page instance
            restaurant_name: Restaurant name
            address_info: Address information

        Returns:
            List of delivery snapshots

        Raises:
            NotImplementedError: Must be implemented by subclass
        """
        pass

    async def run(self, output_file: Optional[str] = None) -> list[dict]:
        """Run the scraper for all addresses and restaurants.

        Args:
            output_file: Output filename

        Returns:
            List of scraped data dictionaries
        """
        all_results = []
        if output_file is None:
            output_file = f"{self.PLATFORM_NAME}_raw.json"

        async with async_playwright() as p:
            self.browser, self.context = await self.create_stealth_context(p)
            self.page = await self.context.new_page()

            for addr_info in ZoneConstants.ZONES:
                logger.info(f"Processing: {addr_info['address']} [{addr_info['zone']}]")

                location_ok = await self.set_location(self.page, addr_info["address"])
                if not location_ok:
                    logger.warning(f"Skipping {addr_info['address']}")
                    continue

                for restaurant in RestaurantConstants.TARGET_RESTAURANTS:
                    results = await self.scrape_restaurant(self.page, restaurant, addr_info)
                    all_results.extend([r.model_dump() for r in results])

                    delay = random.uniform(
                        self.settings.SCRAPER_DELAY_MIN, self.settings.SCRAPER_DELAY_MAX
                    )
                    logger.info(f"Waiting {delay:.1f}s...")
                    await asyncio.sleep(delay)

                output_path = self.output_dir / output_file
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)

            await self.browser.close()

        logger.info(f"Scraping completed. {len(all_results)} records")
        return all_results

    async def close(self):
        """Close browser and cleanup resources."""
        if self.browser:
            await self.browser.close()
