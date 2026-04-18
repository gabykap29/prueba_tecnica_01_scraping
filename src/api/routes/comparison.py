"""Comparison routes for the Rappi Analytics API."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

import scripts.build_live_snapshot as build_snapshot_module
import scripts.scrape_didi_live as scrape_didi_module
import scripts.scrape_rappi_live as scrape_rappi_module
import scripts.scrape_ubereats_live as scrape_ubereats_module
from src.analytics.competitive import (
    compare_product,
    generate_summary,
    live_scrape_status,
    load_current_competitive_data,
    resolve_data_path,
)
from src.shared.constants import RestaurantConstants

router = APIRouter()


def _restaurant_limit_for_product(product: str) -> int:
    """Pick enough target restaurants to cover the requested product."""
    normalized = product.lower()
    if "whopper" in normalized:
        return min(2, len(RestaurantConstants.TARGET_RESTAURANTS))
    if "big mac" in normalized:
        return 1
    return len(RestaurantConstants.TARGET_RESTAURANTS)


async def refresh_live_data_for_product_limited(product: str, limit_rest: int = 1) -> dict:
    """Run a minimal live refresh: 1 address, 1 restaurant per platform."""
    limit_addresses = 1
    limit_restaurants = min(limit_rest, 1)

    scrape_configs = [
        ("rappi", "data/live_rappi_snapshot.csv", scrape_rappi_module.scrape_rappi),
        ("ubereats", "data/live_ubereats_snapshot.csv", scrape_ubereats_module.scrape_ubereats),
        ("didi", "data/live_didi_snapshot.csv", scrape_didi_module.scrape_didi),
    ]

    platform_results = []

    for platform, output_path, scraper_func in scrape_configs:
        try:
            result = await scraper_func(
                output_path=output_path,
                limit_addresses=limit_addresses,
                limit_restaurants=limit_restaurants,
                headless=True,
            )
            platform_results.append(
                {
                    "platform": platform,
                    "status": "completed",
                    "output": str(result),
                }
            )
        except Exception as exc:
            platform_results.append(
                {
                    "platform": platform,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    try:
        snapshot_path = build_snapshot_module.build_snapshot()
        snapshot_status = {"status": "completed", "output": str(snapshot_path)}
    except Exception as exc:
        snapshot_status = {"status": "failed", "error": str(exc)}

    return {
        "attempted": True,
        "limit_addresses": limit_addresses,
        "limit_restaurants": limit_restaurants,
        "platforms": platform_results,
        "snapshot": snapshot_status,
    }


async def refresh_live_data_for_product(product: str) -> dict:
    """Run a focused live refresh before comparing a product."""
    limit_restaurants = _restaurant_limit_for_product(product)
    scrapers = [
        ("rappi", "data/live_rappi_snapshot.csv", scrape_rappi_module.scrape_rappi),
        ("ubereats", "data/live_ubereats_snapshot.csv", scrape_ubereats_module.scrape_ubereats),
        ("didi", "data/live_didi_snapshot.csv", scrape_didi_module.scrape_didi),
    ]
    platform_results = []

    for platform, output_path, scraper_func in scrapers:
        try:
            result = await scraper_func(
                output_path=output_path,
                limit_addresses=1,
                limit_restaurants=limit_restaurants,
                headless=True,
            )
            platform_results.append(
                {
                    "platform": platform,
                    "status": "completed",
                    "output": str(result),
                }
            )
        except Exception as exc:
            platform_results.append(
                {
                    "platform": platform,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    try:
        snapshot_path = build_snapshot_module.build_snapshot()
        snapshot_status = {"status": "completed", "output": str(snapshot_path)}
    except Exception as exc:
        snapshot_status = {"status": "failed", "error": str(exc)}

    return {
        "attempted": True,
        "limit_addresses": 1,
        "limit_restaurants": limit_restaurants,
        "platforms": platform_results,
        "snapshot": snapshot_status,
    }


def _build_data_source(records: list, refresh_result: dict | None) -> dict:
    return {
        "dataset_path": str(resolve_data_path()),
        "live_records": sum(record.source_type == "live" for record in records),
        "backup_records": sum(record.source_type == "backup" for record in records),
        "live_scrape_status": live_scrape_status(),
        "refresh_attempt": refresh_result or {"attempted": False},
    }


def _build_freshness_message(comparison: dict) -> dict:
    results = comparison.get("results", [])
    live_records = sum(row.get("live_records", 0) for row in results)
    backup_records = sum(row.get("backup_records", 0) for row in results)
    platforms_without_live = [row["platform"] for row in results if row.get("live_records", 0) == 0]

    if live_records == 0:
        return {
            "status": "fallback_csv",
            "message": (
                "No se pudo obtener informacion actualizada para este producto; "
                "la comparacion usa el CSV disponible."
            ),
            "live_records": live_records,
            "backup_records": backup_records,
            "platforms_without_live": platforms_without_live,
        }
    if platforms_without_live:
        return {
            "status": "partial_live",
            "message": (
                "Se obtuvo informacion live parcial; las plataformas sin datos live "
                "usan el CSV disponible."
            ),
            "live_records": live_records,
            "backup_records": backup_records,
            "platforms_without_live": platforms_without_live,
        }
    return {
        "status": "live",
        "message": "La comparacion usa informacion actualizada del scrape live.",
        "live_records": live_records,
        "backup_records": backup_records,
        "platforms_without_live": [],
    }


@router.get("/compare")
async def compare_prices(
    product: str = Query(..., description="Product name to compare"),
    zone: Optional[str] = Query(None, description="Zone type: high, mid, periphery"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    refresh: bool = Query(True, description="Attempt a focused live scrape before comparing"),
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
    if refresh:
        limit_rest = 1
        refresh_result = await refresh_live_data_for_product_limited(product, limit_rest)
    else:
        refresh_result = None
    records = load_current_competitive_data()
    comparison = compare_product(product=product, zone_type=zone, records=records)
    comparison["period"] = {
        "start": start_date or min(record.scraped_at for record in records),
        "end": end_date or max(record.scraped_at for record in records),
    }
    comparison["data_source"] = _build_data_source(records, refresh_result)
    comparison["freshness"] = _build_freshness_message(comparison)
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
    summary = generate_summary(load_current_competitive_data())
    metric_key = {
        "price": "avg_total_cost",
        "eta": "avg_eta_min",
        "delivery_fee": "avg_delivery_fee",
        "service_fee": "avg_service_fee",
    }.get(metric, "avg_total_cost")
    zone_rows = [row for row in summary["zones"] if not zone_type or row["zone_type"] == zone_type]
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
