"""API integration smoke tests without optional httpx dependency."""

from src.api.main import app
from src.api.routes.analytics import get_summary
from src.api.routes.comparison import compare_prices
from src.api.routes.health import health_check


def test_health_endpoint():
    payload = health_check()

    assert payload["status"] == "healthy"


def test_compare_endpoint_uses_dataset():
    payload = compare_prices(product="Big Mac", zone="high")

    assert payload["product"] == "Big Mac"
    assert len(payload["results"]) == 3
    assert payload["best_option"] in {"rappi", "ubereats", "didi"}


def test_summary_endpoint_returns_insights():
    payload = get_summary()

    assert payload["records"] == 240
    assert len(payload["top_insights"]) == 5


def test_app_registers_competitive_routes():
    paths = {route.path for route in app.routes}

    assert "/api/v1/analytics/compare" in paths
    assert "/api/v1/analytics/summary" in paths
