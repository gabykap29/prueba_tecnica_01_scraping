"""Data normalization transformers for the ETL pipeline.

This module provides functions for normalizing and validating
scraped data, including price parsing, text cleaning,
and data type conversions.
"""

import re
from typing import Optional


def normalize_product_name(name: str) -> str:
    """Normalize product name by converting to lowercase
    and removing extra whitespace.

    Args:
        name: Product name to normalize

    Returns:
        Normalized product name

    Example:
        >>> normalize_product_name("  Big Mac  ")
        "big mac"
    """
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_price(price: Optional[str | float]) -> Optional[float]:
    """Parse price from various formats to float.

    Args:
        price: Price value (string or number)

    Returns:
        Parsed price as float, or None if invalid

    Example:
        >>> normalize_price("$149.00")
        149.0
        >>> normalize_price(149.0)
        149.0
    """
    if price is None:
        return None

    if isinstance(price, (int, float)):
        return float(price)

    if isinstance(price, str):
        cleaned = price.replace("$", "").replace(",", "").replace(" ", "")
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    return None


def normalize_delivery_fee(fee: Optional[str | float]) -> Optional[float]:
    """Normalize delivery fee to float.

    Args:
        fee: Delivery fee value

    Returns:
        Normalized fee as float
    """
    return normalize_price(fee)


def normalize_zone_type(zone: str) -> str:
    """Normalize zone type to standard values.

    Args:
        zone: Zone type string

    Returns:
        Normalized zone type (high, mid, periphery)
    """
    zone = zone.lower().strip()

    if zone in ("high", "alta"):
        return "high"
    if zone in ("mid", "media"):
        return "mid"
    if zone in ("periphery", "periferica", "periferia"):
        return "periphery"

    return "mid"


def normalize_time(text: Optional[str]) -> Optional[int]:
    """Extract and average time values from text.

    Args:
        text: Text containing time values

    Returns:
        Average time in minutes

    Example:
        >>> normalize_time("25-35 min")
        30
    """
    if not text:
        return None

    numbers = re.findall(r"\d+", text)
    if not numbers:
        return None

    values = [int(n) for n in numbers]
    return sum(values) // len(values)


def normalize_platform(platform: str) -> str:
    """Normalize platform name to standard values.

    Args:
        platform: Platform name string

    Returns:
        Normalized platform name
    """
    platform = platform.lower().strip()

    if "uber" in platform:
        return "ubereats"
    if "rappi" in platform:
        return "rappi"
    if "didi" in platform:
        return "didi"

    return platform


def normalize_address(address: str) -> str:
    """Normalize address string.

    Args:
        address: Address to normalize

    Returns:
        Normalized address
    """
    return re.sub(r"\s+", " ", address.strip())


def normalize_restaurant_name(name: str) -> str:
    """Normalize restaurant name.

    Args:
        name: Restaurant name

    Returns:
        Normalized name
    """
    replacements = {
        "McDonald's": "mcdonalds",
        "McDonalds": "mcdonalds",
        "Burger King": "burgerking",
    }
    normalized = normalize_product_name(name)
    return replacements.get(normalized, normalized)
