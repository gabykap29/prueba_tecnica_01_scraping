"""Tests for competitive analytics helpers."""

from src.analytics.competitive import compare_product, generate_summary, load_competitive_data


def test_load_backup_dataset_has_required_scope():
    records = load_competitive_data()

    assert len(records) == 240
    assert len({record.address for record in records}) == 20
    assert {record.platform for record in records} == {"rappi", "ubereats", "didi"}
    assert len({record.product_name for record in records}) == 4


def test_compare_product_returns_ranked_platforms():
    comparison = compare_product("Big Mac", zone_type="periphery")

    assert comparison["product"] == "Big Mac"
    assert comparison["zone"] == "periphery"
    assert comparison["best_option"] in {"rappi", "ubereats", "didi"}
    assert len(comparison["results"]) == 3
    assert all("avg_total_cost" in row for row in comparison["results"])


def test_summary_generates_five_actionable_insights():
    summary = generate_summary(load_competitive_data())

    assert summary["records"] == 240
    assert len(summary["platform_averages"]) == 3
    assert len(summary["top_insights"]) == 5
    assert {"finding", "impact", "recommendation"} <= set(summary["top_insights"][0])
