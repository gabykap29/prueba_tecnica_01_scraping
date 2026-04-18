"""Analytics helpers for competitive intelligence data.

The functions in this module operate on the structured CSV produced by the
scrapers or by the deterministic backup data generator. They intentionally use
the Python standard library so the report and API can run in constrained demo
environments without extra analysis dependencies.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


DEFAULT_DATA_PATH = Path("sample_data/competitive_snapshot.csv")
PLATFORM_ORDER = ("rappi", "ubereats", "didi")


@dataclass(frozen=True)
class CompetitiveRecord:
    """One comparable product observation from a delivery platform."""

    platform: str
    address: str
    zone_type: str
    restaurant: str
    product_name: str
    product_price: float
    delivery_fee: float
    service_fee: float
    estimated_time_min: int
    active_promo: str
    availability: str
    scraped_at: str
    source_url: str
    search_url: str

    @property
    def total_cost(self) -> float:
        """Final visible cost before promo-specific redemption rules."""
        return round(self.product_price + self.delivery_fee + self.service_fee, 2)

    @property
    def available(self) -> bool:
        """Whether the product/restaurant was visible as orderable."""
        return self.availability.lower() == "available"


def load_competitive_data(path: str | Path = DEFAULT_DATA_PATH) -> list[CompetitiveRecord]:
    """Load competitive observations from a CSV file."""
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Competitive data not found at {csv_path}. Run scripts/generate_sample_data.py "
            "or a platform scraper first."
        )

    records: list[CompetitiveRecord] = []
    with csv_path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            records.append(
                CompetitiveRecord(
                    platform=row["platform"].strip().lower(),
                    address=row["address"].strip(),
                    zone_type=row["zone_type"].strip().lower(),
                    restaurant=row["restaurant"].strip(),
                    product_name=row["product_name"].strip(),
                    product_price=float(row["product_price"]),
                    delivery_fee=float(row["delivery_fee"]),
                    service_fee=float(row["service_fee"]),
                    estimated_time_min=int(float(row["estimated_time_min"])),
                    active_promo=row.get("active_promo", "").strip(),
                    availability=row.get("availability", "available").strip().lower(),
                    scraped_at=row.get("scraped_at", "").strip(),
                    source_url=row.get("source_url", "").strip(),
                    search_url=row.get("search_url", "").strip(),
                )
            )
    return records


def _avg(values: Iterable[float]) -> float:
    values_list = list(values)
    return round(mean(values_list), 2) if values_list else 0.0


def _filter_records(
    records: Iterable[CompetitiveRecord],
    product: str | None = None,
    zone_type: str | None = None,
    restaurant: str | None = None,
) -> list[CompetitiveRecord]:
    filtered = list(records)
    if product:
        product_lower = product.lower()
        filtered = [r for r in filtered if product_lower in r.product_name.lower()]
    if zone_type and zone_type != "all":
        filtered = [r for r in filtered if r.zone_type == zone_type.lower()]
    if restaurant and restaurant != "all":
        restaurant_lower = restaurant.lower()
        filtered = [r for r in filtered if restaurant_lower in r.restaurant.lower()]
    return filtered


def platform_averages(records: Iterable[CompetitiveRecord]) -> list[dict]:
    """Aggregate cost, fees, ETA, promo, and availability by platform."""
    grouped: dict[str, list[CompetitiveRecord]] = defaultdict(list)
    for record in records:
        grouped[record.platform].append(record)

    rows = []
    for platform in PLATFORM_ORDER:
        items = grouped.get(platform, [])
        if not items:
            continue
        promo_count = sum(1 for item in items if item.active_promo)
        rows.append(
            {
                "platform": platform,
                "source_url": items[0].source_url,
                "sample_search_url": items[0].search_url,
                "avg_product_price": _avg(item.product_price for item in items),
                "avg_delivery_fee": _avg(item.delivery_fee for item in items),
                "avg_service_fee": _avg(item.service_fee for item in items),
                "avg_total_cost": _avg(item.total_cost for item in items),
                "avg_eta_min": round(_avg(item.estimated_time_min for item in items)),
                "promo_share": round(promo_count / len(items), 3),
                "availability_rate": round(sum(item.available for item in items) / len(items), 3),
                "records": len(items),
            }
        )
    return rows


def compare_product(
    product: str,
    zone_type: str | None = None,
    records: Iterable[CompetitiveRecord] | None = None,
) -> dict:
    """Compare a product across platforms and return the best option by total cost."""
    source = list(records) if records is not None else load_competitive_data()
    filtered = _filter_records(source, product=product, zone_type=zone_type)
    rows = platform_averages(filtered)
    if not rows:
        return {
            "product": product,
            "zone": zone_type or "all",
            "results": [],
            "best_option": None,
            "rappi_position": "no_data",
            "savings_vs_avg": 0.0,
        }

    best = min(rows, key=lambda row: row["avg_total_cost"])
    total_avg = _avg(row["avg_total_cost"] for row in rows)
    rappi = next((row for row in rows if row["platform"] == "rappi"), None)
    rappi_position = "no_data"
    if rappi:
        delta = rappi["avg_total_cost"] - total_avg
        if abs(delta) <= 3:
            rappi_position = "similar"
        elif delta > 0:
            rappi_position = "more_expensive"
        else:
            rappi_position = "cheaper"

    return {
        "product": product,
        "zone": zone_type or "all",
        "results": rows,
        "best_option": best["platform"],
        "rappi_position": rappi_position,
        "savings_vs_avg": round(total_avg - best["avg_total_cost"], 2),
    }


def zone_summary(records: Iterable[CompetitiveRecord]) -> list[dict]:
    """Aggregate competitiveness by zone type and platform."""
    grouped: dict[tuple[str, str], list[CompetitiveRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.zone_type, record.platform)].append(record)

    rows = []
    for (zone_type, platform), items in sorted(grouped.items()):
        rows.append(
            {
                "zone_type": zone_type,
                "platform": platform,
                "avg_total_cost": _avg(item.total_cost for item in items),
                "avg_eta_min": round(_avg(item.estimated_time_min for item in items)),
                "avg_delivery_fee": _avg(item.delivery_fee for item in items),
                "avg_service_fee": _avg(item.service_fee for item in items),
                "records": len(items),
            }
        )
    return rows


def eta_by_platform(records: Iterable[CompetitiveRecord], restaurant: str | None = None) -> list[dict]:
    """Return ETA statistics by platform."""
    filtered = _filter_records(records, restaurant=restaurant)
    grouped: dict[str, list[int]] = defaultdict(list)
    for record in filtered:
        grouped[record.platform].append(record.estimated_time_min)

    rows = []
    for platform in PLATFORM_ORDER:
        values = grouped.get(platform, [])
        if values:
            rows.append(
                {
                    "platform": platform,
                    "avg_min": round(_avg(values)),
                    "min": min(values),
                    "max": max(values),
                }
            )
    return rows


def promo_summary(records: Iterable[CompetitiveRecord]) -> list[dict]:
    """Count active promotion messages by platform."""
    counter: Counter[tuple[str, str]] = Counter()
    for record in records:
        promo = record.active_promo or "no visible promo"
        counter[(record.platform, promo)] += 1

    return [
        {"platform": platform, "promo": promo, "count": count}
        for (platform, promo), count in counter.most_common(10)
    ]


def top_insights(records: Iterable[CompetitiveRecord]) -> list[dict]:
    """Generate five action-oriented competitive insights."""
    rows = platform_averages(records)
    zones = zone_summary(records)
    rappi = next(row for row in rows if row["platform"] == "rappi")
    competitors = [row for row in rows if row["platform"] != "rappi"]
    cheapest_competitor = min(competitors, key=lambda row: row["avg_total_cost"])
    fastest = min(rows, key=lambda row: row["avg_eta_min"])

    periphery = [row for row in zones if row["zone_type"] == "periphery"]
    rappi_periphery = next(row for row in periphery if row["platform"] == "rappi")
    competitor_periphery = min(
        [row for row in periphery if row["platform"] != "rappi"],
        key=lambda row: row["avg_delivery_fee"],
    )

    fee_gap = round(rappi["avg_total_cost"] - cheapest_competitor["avg_total_cost"], 2)
    periphery_fee_gap = round(
        rappi_periphery["avg_delivery_fee"] - competitor_periphery["avg_delivery_fee"], 2
    )
    promo_leader = max(rows, key=lambda row: row["promo_share"])
    service_fee_leader = min(rows, key=lambda row: row["avg_service_fee"])

    return [
        {
            "finding": (
                f"Rappi is {fee_gap} MXN above {cheapest_competitor['platform']} on average "
                "for the comparable basket."
            ),
            "impact": "Small basket gaps compound in high-frequency fast-food occasions.",
            "recommendation": "Use targeted basket subsidies on products where Rappi is above market.",
            "category": "price_positioning",
        },
        {
            "finding": (
                f"{fastest['platform']} has the lowest ETA at {fastest['avg_eta_min']} min on average."
            ),
            "impact": "ETA differences can shift conversion when prices are similar.",
            "recommendation": "Prioritize courier availability in zones where Rappi ETA is not first.",
            "category": "operational_advantage",
        },
        {
            "finding": (
                f"In periphery zones, Rappi delivery fee is {periphery_fee_gap} MXN above "
                f"{competitor_periphery['platform']}."
            ),
            "impact": "Periphery zones are expansion-sensitive and delivery fees are highly visible.",
            "recommendation": "Test delivery-fee caps in Iztapalapa, Xochimilco, and GAM backup zones.",
            "category": "geographic_variability",
        },
        {
            "finding": (
                f"{promo_leader['platform']} shows visible promos in "
                f"{round(promo_leader['promo_share'] * 100)}% of observations."
            ),
            "impact": "Promo visibility may make competitors feel cheaper before checkout.",
            "recommendation": "Mirror high-visibility promo placements on direct comparison products.",
            "category": "promotion_strategy",
        },
        {
            "finding": (
                f"{service_fee_leader['platform']} has the lowest average service fee at "
                f"{service_fee_leader['avg_service_fee']} MXN."
            ),
            "impact": "Service fees explain total-cost gaps even when item prices are close.",
            "recommendation": "Separate service-fee and delivery-fee diagnostics in weekly pricing reviews.",
            "category": "fee_structure",
        },
    ]


def generate_summary(records: Iterable[CompetitiveRecord] | None = None) -> dict:
    """Build a complete summary for API responses and reports."""
    source = list(records) if records is not None else load_competitive_data()
    addresses = {record.address for record in source}
    products = sorted({record.product_name for record in source})
    return {
        "records": len(source),
        "addresses": len(addresses),
        "platforms": [row["platform"] for row in platform_averages(source)],
        "source_urls": [
            {
                "platform": row["platform"],
                "source_url": row["source_url"],
                "sample_search_url": row["sample_search_url"],
            }
            for row in platform_averages(source)
        ],
        "products": products,
        "platform_averages": platform_averages(source),
        "zones": zone_summary(source),
        "promos": promo_summary(source),
        "top_insights": top_insights(source),
    }
