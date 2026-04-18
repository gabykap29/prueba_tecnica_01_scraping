"""CSV schema and helpers for live competitive scrape output."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


LIVE_FIELDS = [
    "platform",
    "address",
    "zone_type",
    "restaurant",
    "product_name",
    "product_price",
    "delivery_fee",
    "service_fee",
    "estimated_time_min",
    "active_promo",
    "availability",
    "scraped_at",
    "source_url",
    "search_url",
    "evidence_url",
    "error",
]


def write_live_csv(rows: Iterable[dict], output_path: str | Path) -> Path:
    """Write live scrape rows with the canonical competitive schema."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LIVE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in LIVE_FIELDS})
    return path
