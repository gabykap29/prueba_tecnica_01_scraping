"""Platform extractors for the ETL pipeline.

This module provides platform-specific scraper implementations
for Uber Eats, Rappi, and Didi Food.
"""

from ...etl.base_scraper import BaseScraper
from ...etl.models import DeliverySnapshot
from .ubereats import UberEatsScraper
from .rappi import RappiScraper
from .didi import DidiFoodScraper

__all__ = [
    "BaseScraper",
    "DeliverySnapshot",
    "UberEatsScraper",
    "RappiScraper",
    "DidiFoodScraper",
]
