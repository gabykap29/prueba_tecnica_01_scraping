"""Comparison routes backed by the chat agent."""

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
    dates = f" periodo {start_date or ''} {end_date or ''}" if start_date or end_date else ""
    refresh_text = " refrescar" if refresh else ""
    return await _chat_data(
        f"comparar {product}{zone and f' zona {zone}' or ''}{dates}{refresh_text}",
        "analytics-compare",
    )


@router.get("/rankings")
async def get_rankings(
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
    return await _chat_data(
        f"rankings metrica {metric}{zone_type and f' zona {zone_type}' or ''} limite {limit}",
        "analytics-rankings",
    )
