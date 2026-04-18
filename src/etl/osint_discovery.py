"""OSINT-style discovery helpers for indexed delivery platform pages."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Callable
from unicodedata import normalize
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from playwright.async_api import Page

from src.shared.config import get_settings
from src.shared.constants import RestaurantConstants, ScrapingConstants
from src.shared.platform_urls import (
    build_didi_discovery_query,
    build_osint_search_url,
    build_ubereats_discovery_query,
    extract_didi_food_urls,
    extract_ubereats_store_urls,
    is_didi_food_restaurant_url,
    is_ubereats_store_url,
)


@dataclass(frozen=True)
class DiscoveryResult:
    """Result of a public-index discovery attempt."""

    platform: str
    url: str
    search_url: str
    error: str = ""
    provider: str = "html_search"


def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching: remove accents and special chars."""
    return normalize("NFD", text.lower()).encode("ascii", "ignore").decode("ascii")


def product_hint_for_restaurant(restaurant: str) -> str:
    """Pick a product term that helps public search find the right store page."""
    normalized = normalize_text(restaurant)
    if "mcdonald" in normalized:
        return "Big Mac"
    if "burger king" in normalized:
        return "Whopper"
    return RestaurantConstants.TARGET_PRODUCTS[0]


def fetch_search_html(search_url: str, timeout: int = 12) -> str:
    """Fetch a search-result page with a browser-like user agent."""
    request = Request(
        search_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def fetch_serpapi_results(query: str, api_key: str, timeout: int = 20) -> dict:
    """Fetch Google results through SerpApi without exposing the key in logs."""
    params = {
        "engine": "google",
        "q": query,
        "google_domain": "google.com.mx",
        "gl": "mx",
        "hl": "es",
        "num": "10",
        "api_key": api_key,
    }
    request = Request(
        f"https://serpapi.com/search.json?{urlencode(params)}",
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def safe_serpapi_search_url(query: str) -> str:
    """Return the SerpApi request URL without the API key."""
    params = {
        "engine": "google",
        "q": query,
        "google_domain": "google.com.mx",
        "gl": "mx",
        "hl": "es",
        "num": "10",
    }
    return f"https://serpapi.com/search.json?{urlencode(params)}"


def extract_serpapi_links(payload: dict) -> list[str]:
    """Extract candidate result URLs from a SerpApi JSON response."""
    links = []
    for section in ("organic_results", "local_results", "inline_sitelinks"):
        items = payload.get(section, [])
        if isinstance(items, dict):
            items = items.get("places", []) or items.get("results", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            for key in ("link", "source", "website"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    links.append(value)
    return links


def _unique_matching_urls(links: list[str], predicate: Callable[[str], bool]) -> list[str]:
    urls = []
    seen = set()
    for link in links:
        candidate = link.split("#", 1)[0]
        if predicate(candidate) and candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


async def discover_indexed_store_url(
    platform: str,
    restaurant: str,
    address: str,
    search_engine: str = "duckduckgo",
) -> DiscoveryResult:
    """Discover an indexed restaurant/store URL using public search results."""
    normalized_platform = platform.lower().strip()
    product = product_hint_for_restaurant(restaurant)

    if normalized_platform == "didi":
        query = build_didi_discovery_query(
            restaurant=restaurant,
            product=product,
            address=address,
        )
        extractor = extract_didi_food_urls
        predicate = is_didi_food_restaurant_url
    elif normalized_platform == "ubereats":
        query = build_ubereats_discovery_query(
            restaurant=restaurant,
            product=product,
            address=address,
        )
        extractor = extract_ubereats_store_urls
        predicate = is_ubereats_store_url
    else:
        raise ValueError(f"Unsupported OSINT discovery platform: {platform}")

    serpapi_key = get_settings().SERPAPI_API_KEY
    if serpapi_key:
        serpapi_url = safe_serpapi_search_url(query)
        try:
            payload = await asyncio.to_thread(fetch_serpapi_results, query, serpapi_key)
        except (OSError, URLError, json.JSONDecodeError) as exc:
            serpapi_error = f"{normalized_platform}_serpapi_failed: {exc}"
        else:
            urls = _unique_matching_urls(extract_serpapi_links(payload), predicate)
            if urls:
                return DiscoveryResult(
                    platform=normalized_platform,
                    url=urls[0],
                    search_url=serpapi_url,
                    provider="serpapi",
                )
            serpapi_error = f"{normalized_platform}_serpapi_no_indexed_url"
    else:
        serpapi_error = ""

    search_url = build_osint_search_url(query, engine=search_engine)
    try:
        html = await asyncio.to_thread(fetch_search_html, search_url)
    except (OSError, URLError) as exc:
        error = f"{normalized_platform}_discovery_failed: {exc}"
        if serpapi_error:
            error = f"{serpapi_error}; {error}"
        return DiscoveryResult(
            platform=normalized_platform,
            url="",
            search_url=search_url,
            error=error,
        )

    urls = extractor(html)
    if not urls:
        error = f"{normalized_platform}_discovery_no_indexed_url"
        if serpapi_error:
            error = f"{serpapi_error}; {error}"
        return DiscoveryResult(
            platform=normalized_platform,
            url="",
            search_url=search_url,
            error=error,
        )
    return DiscoveryResult(platform=normalized_platform, url=urls[0], search_url=search_url)


async def open_indexed_store_page(page: Page, url: str) -> str:
    """Open a store page and scroll once so lazy-loaded menu text can render."""
    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=ScrapingConstants.PAGE_LOAD_TIMEOUT,
    )
    await page.wait_for_timeout(3000)
    await page.mouse.wheel(0, 700)
    await page.wait_for_timeout(1500)
    try:
        return await page.locator("body").inner_text(timeout=8000)
    except Exception:
        return await page.content()
