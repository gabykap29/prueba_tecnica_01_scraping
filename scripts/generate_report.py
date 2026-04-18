"""Generate the executive HTML report from competitive data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.reporting.competitive_report import write_report


if __name__ == "__main__":
    path = write_report()
    print(f"Wrote {path}")
