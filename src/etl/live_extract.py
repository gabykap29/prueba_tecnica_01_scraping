"""Shared text extraction helpers for live platform scrapers."""

from __future__ import annotations

import re
from typing import Optional

from playwright.async_api import Page


PRICE_RE = re.compile(r"\$\s?([0-9]+(?:[.,][0-9]{1,2})?)")
ETA_RE = re.compile(r"(\d{1,3})\s*(?:-|a)?\s*(\d{1,3})?\s*min", re.IGNORECASE)
PROMO_RE = re.compile(r"(\d{1,2}\s?%|promo|descuento|gratis|env[ií]o)", re.IGNORECASE)


def parse_price_near(text: str, product_name: str) -> Optional[float]:
    """Extract the first price near a product name in rendered page text."""
    product_index = text.lower().find(product_name.lower())
    if product_index == -1:
        return None
    window = text[product_index : product_index + 700]
    match = PRICE_RE.search(window)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def parse_eta(text: str) -> Optional[int]:
    """Extract an average ETA from text such as `25-35 min`."""
    match = ETA_RE.search(text)
    if not match:
        return None
    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) else first
    return (first + second) // 2


def parse_promo(text: str) -> str:
    """Extract a compact visible promo signal from page text."""
    match = PROMO_RE.search(text)
    return match.group(0) if match else ""


async def page_text(page: Page) -> str:
    """Return rendered body text, falling back to HTML content."""
    try:
        return await page.locator("body").inner_text(timeout=8000)
    except Exception:
        return await page.content()
