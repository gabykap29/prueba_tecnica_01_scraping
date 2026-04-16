"""Shared utilities module for the Rappi Analytics application.

This module provides common configuration, constants, exceptions, and utilities
used across all application layers.
"""

from .config import get_settings, get_db_connection, Settings
from .constants import (
    PLATFORMS,
    ZONE_TYPES,
    PlatformConstants,
    ZoneConstants,
    RestaurantConstants,
    ScrapingConstants,
    APIConstants,
)
from .exceptions import (
    RappiAnalyticsException,
    ScraperException,
    ScraperTimeoutException,
    ScraperBlockedException,
    ScraperLocationException,
    DatabaseException,
    ValidationException,
    TransformationException,
    APIException,
    NotFoundException,
)
from .utils import (
    setup_logging,
    random_delay,
    parse_price,
    parse_minutes,
    normalize_text,
    extract_zone_from_address,
    get_current_timestamp,
    safe_float,
    safe_int,
)

__all__ = [
    "get_settings",
    "get_db_connection",
    "Settings",
    "PLATFORMS",
    "ZONE_TYPES",
    "PlatformConstants",
    "ZoneConstants",
    "RestaurantConstants",
    "ScrapingConstants",
    "APIConstants",
    "RappiAnalyticsException",
    "ScraperException",
    "ScraperTimeoutException",
    "ScraperBlockedException",
    "ScraperLocationException",
    "DatabaseException",
    "ValidationException",
    "TransformationException",
    "APIException",
    "NotFoundException",
    "setup_logging",
    "random_delay",
    "parse_price",
    "parse_minutes",
    "normalize_text",
    "extract_zone_from_address",
    "get_current_timestamp",
    "safe_float",
    "safe_int",
]
