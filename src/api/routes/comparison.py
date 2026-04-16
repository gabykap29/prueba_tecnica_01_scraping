"""Comparison routes for the Rappi Analytics API.

This module provides endpoints for comparing prices across platforms,
including price comparison, rankings, and best option detection.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/compare")
def compare_prices(
    product: str = Query(..., description="Product name to compare"),
    zone: Optional[str] = Query(None, description="Zone type: high, mid, periphery"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Compare prices across platforms for a product.

    Args:
        product: Product name to compare
        zone: Zone type filter
        start_date: Start date for comparison period
        end_date: End date for comparison period

    Returns:
        Price comparison across platforms

    Example:
        >>> response = compare_prices(product="Big Mac")
        >>> response["best_option"]
        "ubereats"
    """
    return {
        "product": product,
        "zone": zone or "all",
        "period": {
            "start": start_date or "2026-04-01",
            "end": end_date or "2026-04-16",
        },
        "results": [
            {
                "platform": "ubereats",
                "price": 149.0,
                "delivery_fee": 29.0,
                "total": 178.0,
            },
            {
                "platform": "rappi",
                "price": 145.0,
                "delivery_fee": 35.0,
                "total": 180.0,
            },
            {
                "platform": "didi",
                "price": 159.0,
                "delivery_fee": 25.0,
                "total": 184.0,
            },
        ],
        "best_option": "ubereats",
        "savings_vs_avg": 3.0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/rankings")
def get_rankings(
    metric: str = Query("price", description="Metric: price, eta, delivery_fee"),
    zone_type: Optional[str] = Query(None, description="Zone type: high, mid, periphery"),
    limit: int = Query(10, ge=1, le=100, description="Number of results"),
):
    """Get platform rankings by metric.

    Args:
        metric: Metric to rank by
        zone_type: Zone type filter
        limit: Maximum number of results

    Returns:
        Platform rankings

    Example:
        >>> response = get_rankings(metric="price")
        >>> len(response["rankings"])
        3
    """
    return {
        "metric": metric,
        "zone_type": zone_type or "all",
        "limit": limit,
        "rankings": [
            {
                "rank": 1,
                "platform": "ubereats",
                "restaurant": "McDonald's",
                "metric_value": 178.0,
            },
            {
                "rank": 2,
                "platform": "rappi",
                "restaurant": "McDonald's",
                "metric_value": 180.0,
            },
            {
                "rank": 3,
                "platform": "didi",
                "restaurant": "McDonald's",
                "metric_value": 184.0,
            },
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }
