"""Tests for OSINT discovery providers."""

from types import SimpleNamespace

import pytest

from src.etl import osint_discovery


@pytest.mark.asyncio
async def test_discover_uses_serpapi_when_key_is_configured(monkeypatch):
    def fake_settings():
        return SimpleNamespace(SERPAPI_API_KEY="secret")

    def fake_serpapi_results(query: str, api_key: str) -> dict:
        assert "site:web.didiglobal.com/mx/food/" in query
        assert api_key == "secret"
        return {
            "organic_results": [
                {"link": "https://example.com/not-didi"},
                {
                    "link": (
                        "https://web.didiglobal.com/mx/food/guadalajara-jal/"
                        "mcdonalds-centro/5764607741411459137/"
                    )
                },
            ]
        }

    def fail_html_fetch(search_url: str) -> str:
        raise AssertionError(f"HTML fallback should not run: {search_url}")

    monkeypatch.setattr(osint_discovery, "get_settings", fake_settings)
    monkeypatch.setattr(osint_discovery, "fetch_serpapi_results", fake_serpapi_results)
    monkeypatch.setattr(osint_discovery, "fetch_search_html", fail_html_fetch)

    result = await osint_discovery.discover_indexed_store_url(
        platform="didi",
        restaurant="McDonald's",
        address="Polanco, CDMX",
    )

    assert result.provider == "serpapi"
    assert result.url.endswith("/5764607741411459137/")
    assert "api_key" not in result.search_url


@pytest.mark.asyncio
async def test_discover_falls_back_to_html_when_serpapi_has_no_indexed_url(monkeypatch):
    def fake_settings():
        return SimpleNamespace(SERPAPI_API_KEY="secret")

    def fake_serpapi_results(query: str, api_key: str) -> dict:
        return {"organic_results": [{"link": "https://example.com/not-uber"}]}

    def fake_html_fetch(search_url: str) -> str:
        return """
        <a href="/url?q=https%3A%2F%2Fwww.ubereats.com%2Fmx%2Fstore%2Fmcdonalds-polanco%2FabcDEF123%2F&sa=U">Uber</a>
        """

    monkeypatch.setattr(osint_discovery, "get_settings", fake_settings)
    monkeypatch.setattr(osint_discovery, "fetch_serpapi_results", fake_serpapi_results)
    monkeypatch.setattr(osint_discovery, "fetch_search_html", fake_html_fetch)

    result = await osint_discovery.discover_indexed_store_url(
        platform="ubereats",
        restaurant="McDonald's",
        address="Polanco, CDMX",
    )

    assert result.provider == "html_search"
    assert result.url == "https://www.ubereats.com/mx/store/mcdonalds-polanco/abcDEF123/"
