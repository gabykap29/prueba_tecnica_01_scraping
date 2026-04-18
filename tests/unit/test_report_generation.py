"""Tests for the executive report generator."""

from src.analytics.competitive import load_competitive_data
from src.reporting.competitive_report import build_report_html


def test_report_contains_required_sections():
    html = build_report_html(load_competitive_data())

    assert "Top 5 Actionable Insights" in html
    assert "Average Total Cost by Platform" in html
    assert "Average ETA by Platform" in html
    assert "Average Delivery Fee by Platform" in html
