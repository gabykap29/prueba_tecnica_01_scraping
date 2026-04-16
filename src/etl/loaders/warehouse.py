"""Database loaders for the ETL pipeline.

This module provides functions for loading transformed data
into the PostgreSQL data warehouse, including raw scrape data
and processed analytics.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from psycopg2 import sql

from src.shared.config import get_db_connection

logger = logging.getLogger(__name__)


def load_raw_data(file_path: str) -> list[dict]:
    """Load raw data from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        List of data dictionaries

    Example:
        >>> data = load_raw_data("data/ubereats_raw.json")
        >>> len(data)
        150
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def insert_raw_scrape(
    platform: str,
    address: str,
    zone_type: str,
    restaurant: str,
    product_name: str,
    product_price: Optional[float],
    delivery_fee: Optional[float],
    service_fee: Optional[float],
    estimated_time_min: Optional[int],
    active_promo: Optional[str],
    raw_json: Optional[dict] = None,
    error: Optional[str] = None,
) -> bool:
    """Insert raw scrape data into the warehouse.

    Args:
        platform: Platform name
        address: Full delivery address
        zone_type: Zone classification
        restaurant: Restaurant name
        product_name: Product name
        product_price: Product price
        delivery_fee: Delivery fee
        service_fee: Service fee
        estimated_time_min: Estimated delivery time
        active_promo: Active promotion
        raw_json: Raw JSON data
        error: Error message if failed

    Returns:
        True if insertion successful

    Example:
        >>> result = insert_raw_scrape(
        ...     "ubereats",
        ...     "Polanco, CDMX",
        ...     "high",
        ...     "McDonald's",
        ...     "Big Mac",
        ...     149.0,
        ...     29.0,
        ...     None,
        ...     30,
        ...     "20% off",
        ... )
        >>> result
        True
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO raw_scrape (
                platform_id, address_id, restaurant_id, product_id,
                product_price, delivery_fee, service_fee,
                estimated_time_min, active_promo, raw_json, error
            )
            SELECT
                p.id, a.id, r.id, pr.id,
                %s, %s, %s, %s, %s, %s, %s
            FROM platforms p
            JOIN addresses a ON a.full_address = %s
            JOIN restaurants r ON r.name = %s AND r.platform_id = p.id
            JOIN products pr ON pr.name = %s AND pr.restaurant_id = r.id
            WHERE p.name = %s
            ON CONFLICT DO NOTHING
            """,
            (
                product_price,
                delivery_fee,
                service_fee,
                estimated_time_min,
                active_promo,
                json.dumps(raw_json) if raw_json else None,
                error,
                address,
                restaurant,
                product_name,
                platform,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Inserted raw_scrape: {platform} - {restaurant}")
        return True

    except Exception as e:
        logger.error(f"Insert failed: {e}")
        return False


def insert_price_analytics(
    platform: str,
    address: str,
    restaurant: str,
    product_name: str,
    product_price: Optional[float],
    delivery_fee: Optional[float],
    total_cost: Optional[float],
    estimated_time_min: Optional[int],
    promo_applied: Optional[str],
    scraped_at: datetime,
) -> bool:
    """Insert processed price analytics data.

    Args:
        platform: Platform name
        address: Full delivery address
        restaurant: Restaurant name
        product_name: Product name
        product_price: Product price
        delivery_fee: Delivery fee
        total_cost: Total cost (product + delivery)
        estimated_time_min: Estimated delivery time
        promo_applied: Applied promotion
        scraped_at: Date of scrape

    Returns:
        True if insertion successful
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO price_analytics (
                platform_id, address_id, restaurant_id, product_id,
                product_price, delivery_fee, total_cost,
                estimated_time_min, promo_applied, scraped_at
            )
            SELECT
                p.id, a.id, r.id, pr.id,
                %s, %s, %s, %s, %s, %s
            FROM platforms p
            JOIN addresses a ON a.full_address = %s
            JOIN restaurants r ON r.name = %s AND r.platform_id = p.id
            JOIN products pr ON pr.name = %s AND pr.restaurant_id = r.id
            WHERE p.name = %s
            ON CONFLICT (platform_id, address_id, product_id, scraped_at)
            DO UPDATE SET
                product_price = EXCLUDED.product_price,
                delivery_fee = EXCLUDED.delivery_fee,
                total_cost = EXCLUDED.total_cost
            """,
            (
                product_price,
                delivery_fee,
                total_cost,
                estimated_time_min,
                promo_applied,
                scraped_at.date(),
                address,
                restaurant,
                product_name,
                platform,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Inserted analytics: {platform} - {product_name}")
        return True

    except Exception as e:
        logger.error(f"Analytics insert failed: {e}")
        return False


def batch_load_raw_data(data: list[dict]) -> int:
    """Batch load raw scrape data.

    Args:
        data: List of scrape data dictionaries

    Returns:
        Number of records successfully inserted
    """
    success_count = 0

    for record in data:
        result = insert_raw_scrape(
            platform=record.get("platform"),
            address=record.get("address"),
            zone_type=record.get("zone_type"),
            restaurant=record.get("restaurant"),
            product_name=record.get("product_name"),
            product_price=record.get("product_price"),
            delivery_fee=record.get("delivery_fee"),
            service_fee=record.get("service_fee"),
            estimated_time_min=record.get("estimated_time_min"),
            active_promo=record.get("active_promo"),
            raw_json=record,
            error=record.get("error"),
        )
        if result:
            success_count += 1

    logger.info(f"Batch loaded {success_count}/{len(data)} records")
    return success_count
