"""Data enrichment transformers for the ETL pipeline.

This module provides functions for enriching scraped data
with derived fields, calculated values, and additional context.
"""

import re
from typing import Optional


def enrich_zone_from_address(address: str) -> str:
    """Extract zone type from address string.

    Args:
        address: Full delivery address

    Returns:
        Zone type (high, mid, periphery)

    Example:
        >>> enrich_zone_from_address("Presidente Masaryk 61, Polanco, CDMX")
        "high"
    """
    address_lower = address.lower()

    high_zones = ["polanco", "santa fe", "cuajimalpa", "interlomas"]
    mid_zones = ["centro", "roma", "condesa", "del Valle", "coyoacan"]

    if any(zone in address_lower for zone in high_zones):
        return "high"
    if any(zone in address_lower for zone in mid_zones):
        return "mid"

    return "periphery"


def calculate_total_cost(
    product_price: Optional[float],
    delivery_fee: Optional[float],
) -> Optional[float]:
    """Calculate total cost including delivery fee.

    Args:
        product_price: Product price
        delivery_fee: Delivery fee

    Returns:
        Total cost or None if product_price is None

    Example:
        >>> calculate_total_cost(149.0, 29.0)
        178.0
    """
    if product_price is None:
        return None

    return (product_price or 0) + (delivery_fee or 0)


def enrich_promo_discount(promo_text: Optional[str]) -> Optional[float]:
    """Extract discount percentage from promotion text.

    Args:
        promo_text: Promotion description text

    Returns:
        Discount percentage or None

    Example:
        >>> enrich_promo_discount("20% de descuento")
        20.0
    """
    if not promo_text:
        return None

    matches = re.findall(r"(\d+)\s*%", promo_text)
    if matches:
        return float(matches[0])

    return None


def enrich_time_range(text: Optional[str]) -> dict:
    """Parse time range from text.

    Args:
        text: Time text (e.g., "25-35 min")

    Returns:
        Dictionary with min, max, and average values

    Example:
        >>> enrich_time_range("25-35 min")
        {"min": 25, "max": 35, "avg": 30}
    """
    if not text:
        return {"min": None, "max": None, "avg": None}

    numbers = re.findall(r"\d+", text)

    if len(numbers) >= 2:
        return {
            "min": int(numbers[0]),
            "max": int(numbers[1]),
            "avg": (int(numbers[0]) + int(numbers[1])) // 2,
        }
    if len(numbers) == 1:
        value = int(numbers[0])
        return {"min": value, "max": value, "avg": value}

    return {"min": None, "max": None, "avg": None}


def enrich_restaurant_category(restaurant_name: str) -> str:
    """Infer restaurant category from name.

    Args:
        restaurant_name: Restaurant name

    Returns:
        Category string

    Example:
        >>> enrich_restaurant_category("McDonald's")
        "fast_food"
    """
    name_lower = restaurant_name.lower()

    fast_food_chains = ["mcdonalds", "burger king", "kfc", "wendys", "subway"]
    pizza_chains = ["pizza hut", "dominos", "little caesars", "papalo"]

    if any(chain in name_lower for chain in fast_food_chains):
        return "fast_food"
    if any(chain in name_lower for chain in pizza_chains):
        return "pizza"

    return "restaurant"


def enrich_price_tier(total_cost: Optional[float]) -> str:
    """Classify price into tier.

    Args:
        total_cost: Total cost including delivery

    Returns:
        Price tier (economy, standard, premium)

    Example:
        >>> enrich_price_tier(180.0)
        "standard"
    """
    if total_cost is None:
        return "unknown"

    if total_cost < 150:
        return "economy"
    if total_cost < 250:
        return "standard"

    return "premium"
