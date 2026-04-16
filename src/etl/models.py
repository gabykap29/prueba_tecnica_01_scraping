"""Data models for the Rappi Analytics ETL pipeline.

This module defines Pydantic models for validating and serializing data
throughout the web scraping and data processing pipeline.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DeliverySnapshot(BaseModel):
    """Model representing a single delivery data snapshot.

    This model captures pricing, delivery time, and promotional data
    for a specific product at a specific location.
    """

    platform: str = Field(..., description="Platform name (ubereats, rappi, didi)")
    address: str = Field(..., description="Full delivery address")
    zone_type: str = Field(..., description="Zone classification (high, mid, periphery)")
    restaurant: str = Field(..., description="Restaurant name")
    product_name: str = Field(..., description="Product name")
    product_price: Optional[float] = Field(None, description="Product price in MXN")
    delivery_fee: Optional[float] = Field(None, description="Delivery fee in MXN")
    service_fee: Optional[float] = Field(None, description="Service fee in MXN")
    estimated_time_min: Optional[int] = Field(
        None, description="Estimated delivery time in minutes"
    )
    active_promo: Optional[str] = Field(None, description="Active promotion description")
    scraped_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO timestamp of scrape operation",
    )
    error: Optional[str] = Field(None, description="Error message if scrape failed")

    @field_validator("product_price", "delivery_fee", "service_fee", mode="before")
    @classmethod
    def parse_price(cls, v: Optional[float | str]) -> Optional[float]:
        """Parse price values from various formats to float."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned) if cleaned else None
            except ValueError:
                return None
        return None

    @field_validator("zone_type", mode="before")
    @classmethod
    def normalize_zone(cls, v: str) -> str:
        """Normalize zone type to standard values."""
        zone = v.lower().strip()
        if zone in ("high", "alta"):
            return "high"
        if zone in ("mid", "media"):
            return "mid"
        if zone in ("periphery", "periferica", "periferia"):
            return "periphery"
        return "mid"

    @field_validator("platform", mode="before")
    @classmethod
    def normalize_platform(cls, v: str) -> str:
        """Normalize platform name to standard values."""
        platform = v.lower().strip()
        if "uber" in platform:
            return "ubereats"
        if "rappi" in platform:
            return "rappi"
        if "didi" in platform:
            return "didi"
        return platform


class AddressInfo(BaseModel):
    """Model for address information with zone classification."""

    address: str = Field(..., description="Full delivery address")
    zone: str = Field(..., description="Zone classification")


class RestaurantSearchResult(BaseModel):
    """Model for restaurant search results."""

    name: str = Field(..., description="Restaurant name")
    rating: Optional[float] = Field(None, description="Restaurant rating")
    delivery_time: Optional[str] = Field(None, description="Delivery time estimate")
    delivery_fee: Optional[float] = Field(None, description="Delivery fee")
    is_open: bool = Field(True, description="Whether restaurant is currently open")


class ProductInfo(BaseModel):
    """Model for product information."""

    name: str = Field(..., description="Product name")
    price: Optional[float] = Field(None, description="Product price")
    description: Optional[str] = Field(None, description="Product description")
    available: bool = Field(True, description="Product availability")


class ScrapedData(BaseModel):
    """Model for complete scraped data from a restaurant."""

    platform: str
    address: str
    zone_type: str
    restaurant: str
    products: list[ProductInfo] = Field(default_factory=list)
    delivery_fee: Optional[float] = None
    estimated_time_min: Optional[int] = None
    active_promo: Optional[str] = None
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None
