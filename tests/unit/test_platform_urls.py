"""Tests for platform URL builders."""

from src.shared.platform_urls import (
    build_didi_discovery_query,
    build_didi_discovery_search_url,
    build_didi_food_url,
    build_osint_search_url,
    build_platform_search_url,
    build_ubereats_discovery_query,
    build_rappi_search_url,
    build_ubereats_search_url,
    extract_didi_food_urls,
    extract_ubereats_store_urls,
    is_didi_food_restaurant_url,
    is_ubereats_store_url,
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


def test_didi_discovery_query_targets_indexed_food_pages():
    query = build_didi_discovery_query("McDonald's", "Big Mac", "Polanco, CDMX")

    assert "site:web.didiglobal.com/mx/food/" in query
    assert '"McDonald\'s"' in query
    assert '"Big Mac"' in query
    assert '"Polanco, CDMX"' in query


def test_didi_discovery_search_url_supports_google_and_duckduckgo():
    query = build_didi_discovery_query("McDonald's")

    assert build_didi_discovery_search_url(query).startswith("https://duckduckgo.com/html/?")
    assert build_didi_discovery_search_url(query, "google").startswith(
        "https://www.google.com/search?"
    )


def test_ubereats_discovery_query_targets_indexed_store_pages():
    query = build_ubereats_discovery_query("McDonald's", "Big Mac", "Polanco, CDMX")

    assert "site:www.ubereats.com/mx/store/" in query
    assert '"McDonald\'s"' in query
    assert '"Big Mac"' in query
    assert '"Polanco, CDMX"' in query


def test_osint_search_url_supports_bing():
    assert build_osint_search_url("didi big mac", "bing").startswith(
        "https://www.bing.com/search?"
    )


def test_is_didi_food_restaurant_url_requires_restaurant_id():
    assert is_didi_food_restaurant_url(
        "https://web.didiglobal.com/mx/food/guadalajara-jal/mcdonalds-centro/"
        "5764607741411459137/"
    )
    assert not is_didi_food_restaurant_url("https://web.didiglobal.com/mx/food/")
    assert not is_didi_food_restaurant_url("https://example.com/mx/food/city/store/123/")


def test_is_ubereats_store_url_requires_mexico_store_path():
    assert is_ubereats_store_url(
        "https://www.ubereats.com/mx/store/mcdonalds-polanco/abcDEF123/"
    )
    assert not is_ubereats_store_url("https://www.ubereats.com/mx/feed")
    assert not is_ubereats_store_url("https://web.didiglobal.com/mx/food/city/store/123/")


def test_extract_didi_food_urls_from_search_result_redirects():
    html = """
    <a href="/url?q=https%3A%2F%2Fweb.didiglobal.com%2Fmx%2Ffood%2Fguadalajara-jal%2Fmc%2F5764607741411459137%2F&sa=U">DiDi</a>
    <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fweb.didiglobal.com%2Fmx%2Ffood%2Fcdmx%2Fburger-king%2F1234567890%2F">DiDi DDG</a>
    <a href="https://web.didiglobal.com/mx/food/">Home</a>
    """

    assert extract_didi_food_urls(html) == [
        "https://web.didiglobal.com/mx/food/guadalajara-jal/mc/5764607741411459137/",
        "https://web.didiglobal.com/mx/food/cdmx/burger-king/1234567890/",
    ]


def test_extract_ubereats_store_urls_from_search_result_redirects():
    html = """
    <a href="/url?q=https%3A%2F%2Fwww.ubereats.com%2Fmx%2Fstore%2Fmcdonalds-polanco%2FabcDEF123%2F&sa=U">Uber</a>
    <a href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.ubereats.com%2Fmx%2Fstore%2Fburger-king%2Fxyz_789%2F">Uber DDG</a>
    <a href="https://www.ubereats.com/mx/feed">Feed</a>
    """

    assert extract_ubereats_store_urls(html) == [
        "https://www.ubereats.com/mx/store/mcdonalds-polanco/abcDEF123/",
        "https://www.ubereats.com/mx/store/burger-king/xyz_789/",
    ]


def test_platform_search_url_dispatches_by_platform():
    assert build_platform_search_url("rappi", "Pizza").endswith("/search?query=Pizza")
    assert build_platform_search_url("didi", "Pizza") == "https://web.didiglobal.com/mx/food/"
