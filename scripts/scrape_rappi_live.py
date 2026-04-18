"""Run a focused live Rappi scrape and write a CSV snapshot.

This script intentionally starts narrow: one platform, configurable address and
restaurant limits, and explicit error rows when the site blocks or does not
render comparable data. That makes the live pipeline honest and demo-safe while
preserving the backup CSV as fallback.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import Page, async_playwright

from src.etl.live_schema import write_live_csv
from src.shared.constants import RestaurantConstants, ScrapingConstants, ZoneConstants
from src.shared.platform_urls import PLATFORM_HOME_URLS, build_rappi_search_url


PRICE_RE = re.compile(r"\$\s?([0-9]+(?:[.,][0-9]{1,2})?)")
ETA_RE = re.compile(r"(\d{1,3})\s*(?:-|a)?\s*(\d{1,3})?\s*min", re.IGNORECASE)
PROMO_RE = re.compile(r"(\d{1,2}\s?%|promo|descuento|gratis|env[ií]o)", re.IGNORECASE)


def _parse_price_near(text: str, product_name: str) -> Optional[float]:
    product_index = text.lower().find(product_name.lower())
    if product_index == -1:
        return None
    window = text[product_index : product_index + 700]
    match = PRICE_RE.search(window)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _parse_eta(text: str) -> Optional[int]:
    match = ETA_RE.search(text)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) else first
    return (first + second) // 2


def _parse_promo(text: str) -> str:
    match = PROMO_RE.search(text)
    return match.group(0) if match else ""


async def _page_text(page: Page) -> str:
    try:
        return await page.locator("body").inner_text(timeout=8000)
    except Exception:
        return await page.content()


async def scrape_rappi(
    output_path: str,
    limit_addresses: int,
    limit_restaurants: int,
    headless: bool,
) -> Path:
    """Scrape Rappi search result pages into a live CSV file."""
    rows = []
    addresses = ZoneConstants.ZONES[:limit_addresses]
    restaurants = RestaurantConstants.TARGET_RESTAURANTS[:limit_restaurants]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="es-MX",
            timezone_id="America/Mexico_City",
            extra_http_headers={"Accept-Language": "es-MX,es;q=0.9,en;q=0.8"},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()

        for address_info in addresses:
            for restaurant in restaurants:
                search_url = build_rappi_search_url(restaurant)
                scraped_at = datetime.utcnow().isoformat()
                error = ""
                text = ""
                evidence_url = search_url
                try:
                    await page.goto(
                        search_url,
                        wait_until="domcontentloaded",
                        timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT,
                    )
                    await page.wait_for_timeout(6000)
                    evidence_url = page.url
                    text = await _page_text(page)
                    lowered = text.lower()
                    if any(signal in lowered for signal in ScrapingConstants.BLOCKED_SIGNALS):
                        error = "blocked_or_captcha_detected"
                    elif restaurant.lower().replace("'", "") not in lowered.replace("'", ""):
                        error = "restaurant_not_visible_in_rendered_page"
                except Exception as exc:
                    error = f"navigation_failed: {exc}"

                for product in RestaurantConstants.TARGET_PRODUCTS:
                    product_price = _parse_price_near(text, product) if text else None
                    availability = "available" if product_price is not None and not error else "unknown"
                    rows.append(
                        {
                            "platform": "rappi",
                            "address": address_info["address"],
                            "zone_type": address_info["zone"],
                            "restaurant": restaurant,
                            "product_name": product,
                            "product_price": product_price if product_price is not None else "",
                            "delivery_fee": "",
                            "service_fee": "",
                            "estimated_time_min": _parse_eta(text) or "",
                            "active_promo": _parse_promo(text),
                            "availability": availability,
                            "scraped_at": scraped_at,
                            "source_url": PLATFORM_HOME_URLS["rappi"],
                            "search_url": search_url,
                            "evidence_url": evidence_url,
                            "error": error if product_price is None else error,
                        }
                    )

        await browser.close()

    return write_live_csv(rows, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a focused live Rappi scrape.")
    parser.add_argument("--output", default="data/live_rappi_snapshot.csv")
    parser.add_argument("--limit-addresses", type=int, default=1)
    parser.add_argument("--limit-restaurants", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = await scrape_rappi(
        output_path=args.output,
        limit_addresses=args.limit_addresses,
        limit_restaurants=args.limit_restaurants,
        headless=not args.headed,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
