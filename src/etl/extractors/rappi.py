"""Rappi scraper for the Rappi Analytics ETL pipeline.

This module provides platform-specific scraping logic for Rappi,
including location setting, restaurant search, and product data extraction.
"""

import asyncio
import logging
import random

from playwright.async_api import Page

from src.shared.constants import (
    ScrapingConstants,
    RestaurantConstants,
)
from src.shared.utils import parse_minutes
from src.etl.models import DeliverySnapshot
from src.etl.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class RappiScraper(BaseScraper):
    """Scraper implementation for Rappi platform.

    This class implements platform-specific scraping logic for Rappi,
    including:
    - Location setting for delivery addresses
    - Restaurant search and navigation
    - Product price and delivery fee extraction
    - Promotion detection
    """

    BASE_URL = "https://www.rappi.com.mx"
    PLATFORM_NAME = "rappi"

    async def set_location(self, page: Page, address: str) -> bool:
        """Set delivery location on Rappi.

        Args:
            page: Playwright page instance
            address: Delivery address

        Returns:
            True if location was set successfully
        """
        try:
            await page.goto(
                self.BASE_URL,
                wait_until="domcontentloaded",
                timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT,
            )
            await page.wait_for_timeout(random.randint(1500, 2500))

            address_input = page.locator(
                "input[placeholder*='direccion'], "
                "input[aria-label*='direccion'], "
                "input[data-testid='address-input']"
            ).first
            await address_input.click()
            await page.wait_for_timeout(500)
            await address_input.fill(address)
            await page.wait_for_timeout(1500)

            suggestion = page.locator(
                "[data-testid='suggestion'], .address-suggestion, li[role='option']"
            ).first
            await suggestion.wait_for(timeout=ScrapingConstants.SELECTOR_TIMEOUT)
            await suggestion.click()
            await page.wait_for_timeout(2000)

            logger.info(f"Location set: {address}")
            return True

        except Exception as e:
            logger.warning(f"Failed to set location {address}: {e}")
            return False

    async def search_restaurant(self, page: Page, restaurant_name: str) -> bool:
        """Search for a restaurant on Rappi.

        Args:
            page: Playwright page instance
            restaurant_name: Restaurant name

        Returns:
            True if search was successful
        """
        try:
            search_url = f"{self.BASE_URL}/buscar?q={restaurant_name.replace(' ', '+')}"
            await page.goto(
                search_url, wait_until="networkidle", timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT
            )
            await page.wait_for_timeout(random.randint(2000, 3500))
            return True

        except Exception as e:
            logger.warning(f"Restaurant search failed: {e}")
            return False

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
        """
        snapshots = []

        try:
            if await self.is_blocked(page):
                logger.warning("Blocking detected, waiting...")
                await page.wait_for_timeout(random.randint(8000, 15000))
                return snapshots

            restaurant_cards = page.locator(
                "[data-testid='store-card'], [class*='RestaurantCard'], [class*='tienda']"
            )
            count = await restaurant_cards.count()

            if count == 0:
                logger.warning(f"No results for {restaurant_name}")
                return snapshots

            await restaurant_cards.first.click()
            await page.wait_for_timeout(random.randint(2500, 4000))

            delivery_fee = await self.extract_text(
                page,
                [
                    "[data-testid='delivery-fee'], [class*='envio']",
                    "span:has-text('$'):near(span:has-text('envio'))",
                    "span:has-text('$'):near(span:has-text('delivery'))",
                ],
            )

            est_time = await self.extract_text(
                page,
                [
                    "[data-testid='eta'], [class*='tiempo']",
                    "span:has-text('min'):not(:has-text('$'))",
                ],
            )

            promo = await self.extract_text(
                page,
                [
                    "[data-testid='promo'], [class*='Promo']",
                    "span:has-text('%'):first-of-type",
                ],
            )

            for product in RestaurantConstants.TARGET_PRODUCTS:
                product_price = await self.find_product_price(page, product)
                if product_price:
                    snapshots.append(
                        DeliverySnapshot(
                            platform=self.PLATFORM_NAME,
                            address=address_info["address"],
                            zone_type=address_info["zone"],
                            restaurant=restaurant_name,
                            product_name=product,
                            product_price=product_price,
                            delivery_fee=delivery_fee,
                            estimated_time_min=parse_minutes(est_time),
                            active_promo=promo,
                        )
                    )
                    logger.info(f"Extracted: {product} @ {address_info['address']}")

        except Exception as e:
            logger.error(f"Error scraping {restaurant_name}: {e}")
            snapshots.append(
                DeliverySnapshot(
                    platform=self.PLATFORM_NAME,
                    address=address_info["address"],
                    zone_type=address_info["zone"],
                    restaurant=restaurant_name,
                    product_name="N/A",
                    error=str(e),
                )
            )

        return snapshots

    async def scrape_restaurant(
        self,
        page: Page,
        restaurant_name: str,
        address_info: dict,
    ) -> list[DeliverySnapshot]:
        """Scrape restaurant data from Rappi.

        Args:
            page: Playwright page instance
            restaurant_name: Restaurant name
            address_info: Address information

        Returns:
            List of delivery snapshots
        """
        search_ok = await self.search_restaurant(page, restaurant_name)
        if not search_ok:
            return []

        return await self.extract_product_data(page, restaurant_name, address_info)


async def main():
    """Main entry point for running the scraper directly."""
    scraper = RappiScraper()
    await scraper.run("rappi_raw.json")


if __name__ == "__main__":
    asyncio.run(main())
