"""Comparison routes for the Rappi Analytics API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.analytics.competitive import compare_product, generate_summary, load_competitive_data

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
    records = load_competitive_data()
    comparison = compare_product(product=product, zone_type=zone, records=records)
    comparison["period"] = {
        "start": start_date or min(record.scraped_at for record in records),
        "end": end_date or max(record.scraped_at for record in records),
    }
    comparison["timestamp"] = datetime.utcnow().isoformat()
    return comparison


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
    summary = generate_summary(load_competitive_data())
    metric_key = {
        "price": "avg_total_cost",
        "eta": "avg_eta_min",
        "delivery_fee": "avg_delivery_fee",
        "service_fee": "avg_service_fee",
    }.get(metric, "avg_total_cost")
    zone_rows = [
        row for row in summary["zones"] if not zone_type or row["zone_type"] == zone_type
    ]
    ranked = sorted(zone_rows, key=lambda row: row[metric_key])[:limit]

    return {
        "metric": metric,
        "zone_type": zone_type or "all",
        "limit": limit,
        "rankings": [
            {
                "rank": index + 1,
                "platform": row["platform"],
                "zone_type": row["zone_type"],
                "metric_value": row[metric_key],
            }
            for index, row in enumerate(ranked)
        ],
        "timestamp": datetime.utcnow().isoformat(),
    }
