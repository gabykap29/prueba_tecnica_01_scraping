"""Merge live scrape outputs with the deterministic backup snapshot.

Live rows replace backup rows when they contain a product price. Missing or
blocked live rows are ignored for analytics but preserved in their own
`data/live_*_snapshot.csv` files as audit evidence.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


BACKUP_PATH = Path("sample_data/competitive_snapshot.csv")
DATA_DIR = Path("data")
OUTPUT_PATH = DATA_DIR / "competitive_snapshot.csv"


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        row.get("platform", ""),
        row.get("address", ""),
        row.get("zone_type", ""),
        row.get("restaurant", ""),
        row.get("product_name", ""),
    )


def _has_price(row: dict) -> bool:
    value = str(row.get("product_price", "")).strip()
    if not value:
        return False
    try:
        float(value)
    except ValueError:
        return False
    return True


def build_snapshot() -> Path:
    backup_rows = _read_rows(BACKUP_PATH)
    merged = {_key(row): {**row, "source_type": "backup", "evidence_url": "", "error": ""} for row in backup_rows}

    for live_path in DATA_DIR.glob("live_*_snapshot.csv"):
        for row in _read_rows(live_path):
            if not _has_price(row):
                continue
            key = _key(row)
            backup = merged.get(key, {})
            merged[key] = {
                **backup,
                **{field: value for field, value in row.items() if str(value).strip()},
                "source_type": "live",
            }

    rows = list(merged.values())
    fields = list(dict.fromkeys(field for row in rows for field in row.keys()))
    preferred = [
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
        "stealth_applied",
        "source_type",
    ]
    fields = preferred + [field for field in fields if field not in preferred]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    return OUTPUT_PATH


if __name__ == "__main__":
    print(f"Wrote {build_snapshot()}")
