"""Analytics routes backed by predefined chat-agent questions."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.ai_agent.agent import ai_agent

router = APIRouter()


async def _chat_data(message: str, conversation_id: str) -> dict:
    result = await ai_agent.chat_once(message, conversation_id=conversation_id)
    data = result.get("data") or {}
    return {
        **data,
        "ai_response": result.get("response", ""),
        "chat_states": result.get("states", []),
        "timestamp": data.get("timestamp") or datetime.utcnow().isoformat(),
    }


@router.get("/prices")
async def get_prices(
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
    dates = f" periodo {start_date or ''} {end_date or ''}" if start_date or end_date else ""
    return await _chat_data(
        f"precios{zone_type and f' zona {zone_type}' or ''}"
        f"{restaurant and f' restaurante {restaurant}' or ''}{dates}",
        "analytics-prices",
    )


@router.get("/ETAs")
async def get_et_as(
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
    return await _chat_data(
        f"tiempos {restaurant}{zone and f' zona {zone}' or ''}",
        "analytics-etas",
    )


@router.get("/trends")
async def get_trends(
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
    return await _chat_data(
        f"snapshot {product}{zone and f' zona {zone}' or ''} {days} dias",
        "analytics-trends",
    )


@router.get("/summary")
async def get_summary():
    """Get executive competitive intelligence summary."""
    return await _chat_data("resumen ejecutivo", "analytics-summary")
