"""Run a focused live DiDi Food scrape and write a CSV snapshot."""

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
from src.etl.osint_discovery import (
    discover_indexed_store_url,
    normalize_text,
    open_indexed_store_page,
)
from src.shared.constants import RestaurantConstants, ScrapingConstants, ZoneConstants
from src.shared.platform_urls import PLATFORM_HOME_URLS, build_didi_food_url


async def scrape_didi(
    output_path: str,
    limit_addresses: int,
    limit_restaurants: int,
    headless: bool,
    storage_state: str | None = None,
    didi_url_override: str | None = None,
    search_engine: str = "duckduckgo",
    skip_discovery: bool = False,
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
        didi_url = build_didi_food_url()

        for address_info in addresses:
            for restaurant in restaurants:
                scraped_at = datetime.utcnow().isoformat()
                error = ""
                text = ""
                evidence_url = didi_url
                search_url = didi_url
                normalized_restaurant = normalize_text(restaurant)

                if didi_url_override:
                    try:
                        text = await open_indexed_store_page(page, didi_url_override)
                        evidence_url = page.url
                        search_url = didi_url_override
                    except Exception as e:
                        error = f"didi_url_override_failed: {e}"
                else:
                    discovery_url = ""
                    discovery_error = ""
                    if not skip_discovery:
                        discovery = await discover_indexed_store_url(
                            platform="didi",
                            restaurant=restaurant,
                            address=address_info["address"],
                            search_engine=search_engine,
                        )
                        discovery_url = discovery.url
                        search_url = discovery.search_url
                        discovery_error = discovery.error

                    if discovery_url:
                        try:
                            text = await open_indexed_store_page(page, discovery_url)
                            evidence_url = page.url
                        except Exception as e:
                            error = f"didi_direct_page_failed: {e}"
                    else:
                        error = discovery_error or "didi_discovery_skipped"
                        try:
                            text = await open_indexed_store_page(page, didi_url)
                            evidence_url = page.url
                        except Exception as e:
                            error = f"{error}; didi_home_failed: {e}"

                text_normalized = normalize_text(text)
                captcha_result = await solve_captcha_if_configured(page, evidence_url)
                if captcha_result.solved:
                    await page.wait_for_timeout(3000)
                    text = await page_text(page)
                    text_normalized = normalize_text(text)
                if captcha_result.detected and not captcha_result.solved:
                    error = captcha_result.error
                elif any(signal in text.lower() for signal in ScrapingConstants.BLOCKED_SIGNALS):
                    error = "blocked_or_captcha_detected"

                for product in RestaurantConstants.TARGET_PRODUCTS:
                    product_price = parse_price_near(text, product) if text else None

                    if not product_price and normalized_restaurant in text_normalized:
                        normalized_product = normalize_text(product)
                        if normalized_product not in text_normalized:
                            error = "product_not_found"

                    rows.append(
                        {
                            "platform": "didi",
                            "address": address_info["address"],
                            "zone_type": address_info["zone"],
                            "restaurant": restaurant,
                            "product_name": product,
                            "product_price": product_price if product_price is not None else "",
                            "delivery_fee": "",
                            "service_fee": "",
                            "estimated_time_min": parse_eta(text) or "",
                            "active_promo": parse_promo(text),
                            "availability": "available"
                            if product_price is not None and not error
                            else "unknown",
                            "scraped_at": scraped_at,
                            "source_url": PLATFORM_HOME_URLS["didi"],
                            "search_url": search_url,
                            "evidence_url": evidence_url,
                            "error": error if product_price is None else "",
                            "stealth_applied": stealth_applied,
                        }
                    )

        await context.close()
        await browser.close()

    return write_live_csv(rows, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a focused live DiDi Food scrape.")
    parser.add_argument("--output", default="data/live_didi_snapshot.csv")
    parser.add_argument("--limit-addresses", type=int, default=1)
    parser.add_argument("--limit-restaurants", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--storage-state", default=None)
    parser.add_argument(
        "--didi-url",
        default=None,
        help="Direct indexed DiDi restaurant URL to scrape before using discovery.",
    )
    parser.add_argument(
        "--search-engine",
        default="duckduckgo",
        choices=("duckduckgo", "google", "bing"),
        help="Public search engine used to discover indexed DiDi URLs.",
    )
    parser.add_argument(
        "--skip-discovery",
        action="store_true",
        help="Skip public-search discovery and use the DiDi Food entry point fallback.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = await scrape_didi(
        output_path=args.output,
        limit_addresses=args.limit_addresses,
        limit_restaurants=args.limit_restaurants,
        headless=not args.headed,
        storage_state=args.storage_state,
        didi_url_override=args.didi_url,
        search_engine=args.search_engine,
        skip_discovery=args.skip_discovery,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
