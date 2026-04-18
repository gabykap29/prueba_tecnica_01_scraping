"""Platform URL builders used by scrapers, data exports, and UI references."""

from __future__ import annotations

import base64
import json
import re
from html.parser import HTMLParser
from typing import Callable
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse


PLATFORM_HOME_URLS = {
    "rappi": "https://www.rappi.com.mx",
    "ubereats": "https://www.ubereats.com/mx",
    "didi": "https://web.didiglobal.com/mx/food/",
}


def build_rappi_search_url(query: str) -> str:
    """Build the current Rappi Mexico search URL."""
    return f"{PLATFORM_HOME_URLS['rappi']}/search?query={quote(query)}"


def build_ubereats_search_url(
    query: str,
    address: str,
    latitude: float = 19.432608,
    longitude: float = -99.133209,
    reference: str = "sample_reference",
) -> str:
    """Build an Uber Eats Mexico search URL.

    Uber Eats search URLs commonly include a base64-encoded `pl` location
    payload. In live scraping the session location is normally set through the
    UI first; this URL is a reproducible navigation reference for the selected
    query and address.
    """
    payload = {
        "address": address,
        "reference": reference,
        "referenceType": "google_places",
        "latitude": latitude,
        "longitude": longitude,
    }
    encoded_payload = base64.b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")
    params = {
        "pl": encoded_payload,
        "q": query,
        "sc": "SEARCH_BAR",
        "searchType": "GLOBAL_SEARCH",
        "vertical": "ALL",
    }
    return f"{PLATFORM_HOME_URLS['ubereats']}/search?{urlencode(params)}"


def build_didi_food_url() -> str:
    """Return the DiDi Food Mexico entry point."""
    return PLATFORM_HOME_URLS["didi"]


def build_didi_discovery_query(
    restaurant: str,
    product: str = "",
    address: str = "",
) -> str:
    """Build an external-search query for indexed DiDi Food restaurant pages."""
    terms = [
        "site:web.didiglobal.com/mx/food/",
        f'"{restaurant}"',
    ]
    if product:
        terms.append(f'"{product}"')
    if address:
        terms.append(f'"{address}"')
    terms.append("Mexico")
    return " ".join(terms)


def build_ubereats_discovery_query(
    restaurant: str,
    product: str = "",
    address: str = "",
) -> str:
    """Build an external-search query for indexed Uber Eats store pages."""
    terms = [
        "site:www.ubereats.com/mx/store/",
        f'"{restaurant}"',
    ]
    if product:
        terms.append(f'"{product}"')
    if address:
        terms.append(f'"{address}"')
    terms.append("Mexico")
    return " ".join(terms)


def build_osint_search_url(query: str, engine: str = "duckduckgo") -> str:
    """Build a public search URL for an OSINT discovery query."""
    normalized = engine.lower().strip()
    if normalized == "google":
        return f"https://www.google.com/search?{urlencode({'q': query})}"
    if normalized in {"duckduckgo", "ddg"}:
        return f"https://duckduckgo.com/html/?{urlencode({'q': query})}"
    if normalized == "bing":
        return f"https://www.bing.com/search?{urlencode({'q': query})}"
    raise ValueError(f"Unsupported search engine: {engine}")


def build_didi_discovery_search_url(query: str, engine: str = "duckduckgo") -> str:
    """Build a public search URL for discovering indexed DiDi restaurant pages."""
    return build_osint_search_url(query, engine=engine)


def is_didi_food_restaurant_url(url: str) -> bool:
    """Return True when a URL looks like an indexed DiDi Food restaurant page."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != "web.didiglobal.com":
        return False
    return re.fullmatch(r"/mx/food/[^/]+/[^/]+/\d+/?", parsed.path) is not None


def is_ubereats_store_url(url: str) -> bool:
    """Return True when a URL looks like an indexed Uber Eats Mexico store page."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() not in {"www.ubereats.com", "ubereats.com"}:
        return False
    return re.fullmatch(r"/mx/store/[^/]+/[^/]+/?", parsed.path) is not None


def _unwrap_search_result_url(url: str) -> str:
    """Extract the target URL from common search-result redirect wrappers."""
    parsed = urlparse(unquote(url))
    params = parse_qs(parsed.query)
    for key in ("q", "url", "uddg"):
        if key in params and params[key]:
            return params[key][0]
    return unquote(url)


def _extract_urls(search_html: str, predicate: Callable[[str], bool]) -> list[str]:
    """Extract unique URLs from search-result HTML using a platform predicate."""
    parser = _HrefExtractor()
    parser.feed(search_html)

    urls: list[str] = []
    seen = set()
    for href in parser.hrefs:
        candidate = _unwrap_search_result_url(href).split("#", 1)[0]
        if predicate(candidate) and candidate not in seen:
            seen.add(candidate)
            urls.append(candidate)
    return urls


class _HrefExtractor(HTMLParser):
    """Collect href values from a small search-result HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def extract_didi_food_urls(search_html: str) -> list[str]:
    """Extract unique DiDi Food restaurant URLs from search-result HTML."""
    return _extract_urls(search_html, is_didi_food_restaurant_url)


def extract_ubereats_store_urls(search_html: str) -> list[str]:
    """Extract unique Uber Eats store URLs from search-result HTML."""
    return _extract_urls(search_html, is_ubereats_store_url)


def build_platform_search_url(platform: str, query: str, address: str = "") -> str:
    """Build a platform-specific URL for a restaurant/product query."""
    normalized = platform.lower().strip()
    if normalized == "rappi":
        return build_rappi_search_url(query)
    if normalized == "ubereats":
        return build_ubereats_search_url(query=query, address=address or "CDMX")
    if normalized == "didi":
        return build_didi_food_url()
    raise ValueError(f"Unsupported platform: {platform}")
