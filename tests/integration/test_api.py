"""API integration smoke tests without optional httpx dependency."""

import pytest

from src.api.main import app
from src.api.routes.analytics import get_summary
from src.api.routes.comparison import compare_prices
from src.api.routes.health import health_check
from src.api.routes import knowledge_base


def test_health_endpoint():
    payload = health_check()

    assert payload["status"] == "healthy"


@pytest.mark.asyncio
async def test_compare_endpoint_uses_dataset():
    payload = await compare_prices(product="Big Mac", zone="high", refresh=False)

    assert payload["product"] == "Big Mac"
    assert len(payload["results"]) == 3
    assert payload["best_option"] in {"rappi", "ubereats", "didi"}
    assert payload["data_source"]["dataset_path"]
    assert "live_records" in payload["data_source"]
    assert "backup_records" in payload["data_source"]
    assert payload["data_source"]["refresh_attempt"]["attempted"] is False
    assert payload["freshness"]["status"] in {"live", "partial_live", "fallback_csv"}


def test_summary_endpoint_returns_insights():
    payload = get_summary()

    assert payload["records"] == 240
    assert len(payload["top_insights"]) == 5


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
