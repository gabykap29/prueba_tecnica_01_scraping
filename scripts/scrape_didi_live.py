"""Run a focused live DiDi Food scrape and write a CSV snapshot."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.async_api import async_playwright

from src.etl.live_extract import page_text, parse_eta, parse_price_near, parse_promo
from src.etl.live_schema import write_live_csv
from src.shared.constants import RestaurantConstants, ScrapingConstants, ZoneConstants
from src.shared.platform_urls import PLATFORM_HOME_URLS, build_didi_food_url


async def scrape_didi(
    output_path: str,
    limit_addresses: int,
    limit_restaurants: int,
    headless: bool,
) -> Path:
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
        didi_url = build_didi_food_url()

        for address_info in addresses:
            for restaurant in restaurants:
                scraped_at = datetime.utcnow().isoformat()
                error = ""
                text = ""
                evidence_url = didi_url
                try:
                    await page.goto(
                        didi_url,
                        wait_until="domcontentloaded",
                        timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT,
                    )
                    await page.wait_for_timeout(8000)
                    evidence_url = page.url
                    text = await page_text(page)
                    lowered = text.lower()
                    if any(signal in lowered for signal in ScrapingConstants.BLOCKED_SIGNALS):
                        error = "blocked_or_captcha_detected"
                    elif restaurant.lower().replace("'", "") not in lowered.replace("'", ""):
                        error = "restaurant_not_visible_in_rendered_page"
                except Exception as exc:
                    error = f"navigation_failed: {exc}"

                for product in RestaurantConstants.TARGET_PRODUCTS:
                    product_price = parse_price_near(text, product) if text else None
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
                            "availability": "available" if product_price is not None and not error else "unknown",
                            "scraped_at": scraped_at,
                            "source_url": PLATFORM_HOME_URLS["didi"],
                            "search_url": didi_url,
                            "evidence_url": evidence_url,
                            "error": error if product_price is None else error,
                        }
                    )

        await browser.close()

    return write_live_csv(rows, output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a focused live DiDi Food scrape.")
    parser.add_argument("--output", default="data/live_didi_snapshot.csv")
    parser.add_argument("--limit-addresses", type=int, default=1)
    parser.add_argument("--limit-restaurants", type=int, default=1)
    parser.add_argument("--headed", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    path = await scrape_didi(
        output_path=args.output,
        limit_addresses=args.limit_addresses,
        limit_restaurants=args.limit_restaurants,
        headless=not args.headed,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
