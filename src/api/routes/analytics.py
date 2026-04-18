"""Analytics routes for the Rappi Analytics API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.analytics.competitive import (
    compare_product,
    eta_by_platform,
    generate_summary,
    load_competitive_data,
    platform_averages,
    promo_summary,
)

router = APIRouter()


@router.get("/prices")
def get_prices(
    zone_type: Optional[str] = Query(None, description="Zone type: high, mid, periphery"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    restaurant: Optional[str] = Query(None, description="Filter by restaurant"),
):
    """Get price analytics by zone or restaurant.

    Args:
        zone_type: Zone type filter
        start_date: Start date for period
        end_date: End date for period
        restaurant: Restaurant filter

    Returns:
        Price analytics with averages and promotions

    Example:
        >>> response = get_prices(zone_type="high")
        >>> response["avg_delivery_fee"]
        32.5
    """
    records = load_competitive_data()
    filtered = [
        record
        for record in records
        if (not zone_type or record.zone_type == zone_type)
        and (not restaurant or restaurant.lower() in record.restaurant.lower())
    ]
    averages = platform_averages(filtered)
    avg_delivery_fee = (
        round(sum(row["avg_delivery_fee"] for row in averages) / len(averages), 2)
        if averages
        else 0
    )
    avg_eta_min = (
        round(sum(row["avg_eta_min"] for row in averages) / len(averages)) if averages else 0
    )

    return {
        "zone_type": zone_type or "all",
        "period": {
            "start": start_date or min(record.scraped_at for record in records),
            "end": end_date or max(record.scraped_at for record in records),
        },
        "restaurant": restaurant or "all",
        "avg_delivery_fee": avg_delivery_fee,
        "avg_eta_min": avg_eta_min,
        "total_records": len(filtered),
        "platform_averages": averages,
        "top_promos": promo_summary(filtered),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/ETAs")
def get_et_as(
    restaurant: str = Query(..., description="Restaurant name"),
    zone: Optional[str] = Query(None, description="Zone type: high, mid, periphery"),
):
    """Get delivery time analytics for a restaurant.

    Args:
        restaurant: Restaurant name
        zone: Zone type filter

    Returns:
        ETA statistics by platform

    Example:
        >>> response = get_et_as(restaurant="McDonald's")
        >>> len(response["ETAs"])
        3
    """
    records = load_competitive_data()
    etas = eta_by_platform(records, restaurant=restaurant)
    return {
        "restaurant": restaurant,
        "zone": zone or "all",
        "ETAs": etas,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/trends")
def get_trends(
    product: str = Query(..., description="Product name"),
    zone: Optional[str] = Query(None, description="Zone type"),
    days: int = Query(7, ge=1, le=30, description="Number of days"),
):
    """Get price trends over time.

    Args:
        product: Product name
        zone: Zone type filter
        days: Number of days of history

    Returns:
        Price trends by date

    Example:
        >>> response = get_trends(product="Big Mac", days=7)
        >>> len(response["trends"])
        7
    """
    records = load_competitive_data()
    comparison = compare_product(product=product, zone_type=zone, records=records)
    return {
        "product": product,
        "zone": zone or "all",
        "days": days,
        "note": "Single-snapshot backup data is available; multiple scheduled scrapes are needed for a real time series.",
        "snapshot": comparison["results"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/summary")
def get_summary():
    """Get executive competitive intelligence summary."""
    return {
        **generate_summary(load_competitive_data()),
        "timestamp": datetime.utcnow().isoformat(),
    }
