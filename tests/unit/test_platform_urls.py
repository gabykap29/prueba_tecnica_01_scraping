"""Tests for platform URL builders."""

from src.shared.platform_urls import (
    build_didi_food_url,
    build_platform_search_url,
    build_rappi_search_url,
    build_ubereats_search_url,
)


def test_rappi_search_url_uses_query_param():
    assert build_rappi_search_url("Pizza") == "https://www.rappi.com.mx/search?query=Pizza"


def test_ubereats_search_url_contains_location_payload_and_query():
    url = build_ubereats_search_url("McDonald's", "Francesco Pizza Napoletana")

    assert url.startswith("https://www.ubereats.com/mx/search?")
    assert "pl=" in url
    assert "q=McDonald%27s" in url
    assert "searchType=GLOBAL_SEARCH" in url
    assert "vertical=ALL" in url


def test_didi_food_url_uses_web_entrypoint():
    assert build_didi_food_url() == "https://web.didiglobal.com/mx/food/"


def test_platform_search_url_dispatches_by_platform():
    assert build_platform_search_url("rappi", "Pizza").endswith("/search?query=Pizza")
    assert build_platform_search_url("didi", "Pizza") == "https://web.didiglobal.com/mx/food/"
