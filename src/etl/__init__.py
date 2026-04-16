"""ETL module for the Rappi Analytics application.

This module provides Extract, Transform, Load functionality for
web scraping data from multiple food delivery platforms.

Submodules:
    - models: Pydantic models for data validation
    - base_scraper: Base scraper abstract class
    - extractors: Platform-specific scrapers
    - transformers: Data normalization and enrichment
    - loaders: Database loading utilities
"""

from .models import (
    DeliverySnapshot,
    AddressInfo,
    RestaurantSearchResult,
    ProductInfo,
    ScrapedData,
)
from .base_scraper import BaseScraper

__all__ = [
    "DeliverySnapshot",
    "AddressInfo",
    "RestaurantSearchResult",
    "ProductInfo",
    "ScrapedData",
    "BaseScraper",
]
