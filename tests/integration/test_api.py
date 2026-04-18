"""API integration smoke tests without optional httpx dependency."""

import pytest

from src.api.main import app
from src.api.routes.analytics import get_summary
from src.api.routes.comparison import compare_prices, get_rankings
from src.api.routes.health import health_check
from src.api.routes import knowledge_base
from src.ai_agent.agent import ai_agent
from src.ai_agent.models import DeliveryPriceData


def test_health_endpoint():
    payload = health_check()

    assert payload["status"] == "healthy"


@pytest.mark.asyncio
async def test_compare_endpoint_uses_live_agent(monkeypatch):
    async def fake_search_platform(restaurant, product, platform, location):
        prices = {"rappi": 120, "ubereats": 110, "didi": 105}
        return DeliveryPriceData(
            platform=platform,
            restaurant=restaurant,
            product_name=product,
            product_price=prices[platform],
            delivery_fee=20,
            service_fee=5,
            estimated_time_min=30,
            source_url=f"https://example.com/{platform}",
            confidence=0.8,
        )

    monkeypatch.setattr(ai_agent, "_search_platform", fake_search_platform)

    payload = await compare_prices(product="Big Mac", zone="high", refresh=False)

    assert payload["product"] == "Big Mac"
    assert payload["source_type"] == "live_agent"
    assert payload["fallback_used"] is False
    assert len(payload["results"]) == 3
    assert len(payload["sources"]) == 3
    assert payload["sources"][0]["url"].startswith("https://example.com/")
    assert payload["best_option"] == "didi"
    assert payload["plotly"]["data"]
    assert payload["ai_response"]


@pytest.mark.asyncio
async def test_rankings_endpoint_uses_live_agent(monkeypatch):
    async def fake_search_platform(restaurant, product, platform, location):
        prices = {"rappi": 120, "ubereats": 110, "didi": 105}
        return DeliveryPriceData(
            platform=platform,
            restaurant=restaurant,
            product_name=product,
            product_price=prices[platform],
            delivery_fee=10 if platform == "didi" else 25,
            service_fee=5,
            estimated_time_min=30,
            source_url=f"https://example.com/{platform}",
            confidence=0.8,
        )

    monkeypatch.setattr(ai_agent, "_search_platform", fake_search_platform)

    payload = await get_rankings(metric="delivery_fee", zone_type=None, limit=10)

    assert payload["source_type"] == "live_agent"
    assert payload["rankings"]
    assert payload["sources"]
    assert payload["rankings"][0]["platform"] == "didi"
    assert payload["plotly"]["data"]


@pytest.mark.asyncio
async def test_summary_endpoint_returns_live_agent_insights(monkeypatch):
    async def fake_search_platform(restaurant, product, platform, location):
        prices = {"rappi": 120, "ubereats": 110, "didi": 105}
        return DeliveryPriceData(
            platform=platform,
            restaurant=restaurant,
            product_name=product,
            product_price=prices[platform],
            delivery_fee=10 if platform == "didi" else 25,
            service_fee=5,
            estimated_time_min=25 if platform == "ubereats" else 35,
            source_url=f"https://example.com/{platform}",
            confidence=0.8,
        )

    monkeypatch.setattr(ai_agent, "_search_platform", fake_search_platform)

    payload = await get_summary()

    assert payload["source_type"] == "live_agent"
    assert payload["records"] == 6
    assert payload["top_insights"]
    assert payload["sources"]
    assert payload["plotly"]["platform_costs"]["data"]


def test_app_registers_competitive_routes():
    paths = {route.path for route in app.routes}

    assert "/api/v1/analytics/compare" in paths
    assert "/api/v1/analytics/summary" in paths


def test_clear_database_is_best_effort_when_postgres_is_unavailable(monkeypatch):
    def raise_connection_error():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(knowledge_base, "get_db_connection", raise_connection_error)

    result = knowledge_base.clear_database()

    assert result["status"] == "skipped"
    assert "connection refused" in result["error"]
