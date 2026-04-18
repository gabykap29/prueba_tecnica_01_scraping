"""Platform URL builders used by scrapers, data exports, and UI references."""

from __future__ import annotations

import base64
import json
from urllib.parse import quote, urlencode


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
