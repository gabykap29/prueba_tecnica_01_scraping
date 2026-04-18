"""Run a focused live Uber Eats scrape and write a CSV snapshot."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright

from src.etl.browser import create_stealth_page
from src.etl.captcha_solver import solve_captcha_if_configured
from src.etl.live_extract import page_text, parse_eta, parse_price_near, parse_promo
from src.etl.live_schema import write_live_csv
from src.shared.constants import RestaurantConstants, ScrapingConstants, ZoneConstants
from src.shared.platform_urls import PLATFORM_HOME_URLS, build_ubereats_search_url


async def scrape_ubereats(
    output_path: str,
    limit_addresses: int,
    limit_restaurants: int,
    headless: bool,
    storage_state: str | None = None,
) -> Path:
    rows = []
    addresses = ZoneConstants.ZONES[:limit_addresses]
    restaurants = RestaurantConstants.TARGET_RESTAURANTS[:limit_restaurants]

    async with async_playwright() as playwright:
        browser, context, page, stealth_applied = await create_stealth_page(
            playwright,
            headless=headless,
            storage_state=storage_state,
        )

        for address_info in addresses:
            for restaurant in restaurants:
                search_url = build_ubereats_search_url(
                    query=restaurant,
                    address=address_info["address"],
                )
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
                    await page.wait_for_timeout(8000)
                    evidence_url = page.url
                    text = await page_text(page)
                    lowered = text.lower()
                    captcha_result = await solve_captcha_if_configured(page, evidence_url)
                    if captcha_result.solved:
                        await page.wait_for_timeout(3000)
                        text = await page_text(page)
                        lowered = text.lower()
                    if captcha_result.detected and not captcha_result.solved:
                        error = captcha_result.error
                    elif any(signal in lowered for signal in ScrapingConstants.BLOCKED_SIGNALS):
                        error = "blocked_or_captcha_detected"
                    elif restaurant.lower().replace("'", "") not in lowered.replace("'", ""):
                        error = "restaurant_not_visible_in_rendered_page"
                except Exception as exc:
                    error = f"navigation_failed: {exc}"

                for product in RestaurantConstants.TARGET_PRODUCTS:
                    product_price = parse_price_near(text, product) if text else None
                    rows.append(
                        {
                            "platform": "ubereats",
                            "address": address_info["address"],
                            "zone_type": address_info["zone"],
                            "restaurant": restaurant,
                            "product_name": product,
                            "product_price": product_price if product_price is not None else "",
                            "delivery_fee": "",
                            "service_fee": "",
                            "estimated_time_min": parse_eta(text) or "",
                            "active_promo": parse_promo(text),
                            "availability": "available" if product_price is not None and not error else "unknown",
                            "scraped_at": scraped_at,
                            "source_url": PLATFORM_HOME_URLS["ubereats"],
                            "search_url": search_url,
                            "evidence_url": evidence_url,
                            "error": error if product_price is None else error,
                            "stealth_applied": stealth_applied,
                        }
                    )

        await context.close()
        await browser.close()

    return write_live_csv(rows, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a focused live Uber Eats scrape.")
    parser.add_argument("--output", default="data/live_ubereats_snapshot.csv")
    parser.add_argument("--limit-addresses", type=int, default=1)
    parser.add_argument("--limit-restaurants", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--storage-state", default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = await scrape_ubereats(
        output_path=args.output,
        limit_addresses=args.limit_addresses,
        limit_restaurants=args.limit_restaurants,
        headless=not args.headed,
        storage_state=args.storage_state,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
