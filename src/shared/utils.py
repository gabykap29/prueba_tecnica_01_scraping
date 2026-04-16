"""Utility functions module for the Rappi Analytics application.

This module provides common utility functions used across the application
for data processing, logging, and common operations.
"""

import logging
import random
import re
from datetime import datetime
from typing import Any, Optional


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure application logging.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")
    return logging.getLogger(__name__)


def random_delay(min_seconds: float = 3.0, max_seconds: float = 6.0) -> float:
    """Generate a random delay for rate limiting.

    Args:
        min_seconds: Minimum delay in seconds
        max_seconds: Maximum delay in seconds

    Returns:
        Random delay in seconds
    """
    return random.uniform(min_seconds, max_seconds)


def parse_price(price: Any) -> Optional[float]:
    """Parse price string or number to float.

    Args:
        price: Price value (string or number)

    Returns:
        Parsed price as float, or None if invalid

    Example:
        >>> parse_price("$149.00")
        149.0
        >>> parse_price(149.0)
        149.0
    """
    if price is None:
        return None

    if isinstance(price, (int, float)):
        return float(price)

    if isinstance(price, str):
        cleaned = price.replace("$", "").replace(",", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    return None


def parse_minutes(text: Optional[str]) -> Optional[int]:
    """Parse time text to extract minutes.

    Args:
        text: Text containing minute values (e.g., "25-35 min")

    Returns:
        Average minutes as integer, or None if not found

    Example:
        >>> parse_minutes("25-35 min")
        30
        >>> parse_minutes("30 min")
        30
    """
    if not text:
        return None

    nums = re.findall(r"\d+", text)
    if not nums:
        return None

    values = [int(n) for n in nums]
    return sum(values) // len(values)


def normalize_text(text: Optional[str]) -> Optional[str]:
    """Normalize text by removing extra whitespace and converting to lowercase.

    Args:
        text: Text to normalize

    Returns:
        Normalized text, or None if input is None

    Example:
        >>> normalize_text("  McDonald's  ")
        "mcdonald's"
    """
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip().lower())


def extract_zone_from_address(address: str) -> str:
    """Extract zone type from address string.

    Args:
        address: Full address string

    Returns:
        Zone type (high, mid, or periphery)

    Example:
        >>> extract_zone_from_address("Presidente Masaryk 61, Polanco, CDMX")
        "high"
    """
    address_lower = address.lower()
    high_zones = ["polanco", "santa fe", "cuajimalpa", "interlomas", "bosque"]
    mid_zones = ["roma", "condesa", "del valle", "coyoacan", "centro", "san angel"]
    periphery_zones = [
        "iztapalapa",
        "xochimilco",
        "gustavo",
        "vallejo",
        "tlahuac",
        "texcoco",
    ]

    if any(zone in address_lower for zone in high_zones):
        return "high"
    if any(zone in address_lower for zone in mid_zones):
        return "mid"
    return "periphery"


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format.

    Returns:
        Current timestamp as ISO format string
    """
    return datetime.utcnow().isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer with default.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default
