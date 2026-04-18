"""Run all platform scrapers sequentially with failure isolation."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.etl.extractors.didi import DidiFoodScraper
from src.etl.extractors.rappi import RappiScraper
from src.etl.extractors.ubereats import UberEatsScraper


SCRAPERS = (
    (RappiScraper, "rappi_raw.json"),
    (UberEatsScraper, "ubereats_raw.json"),
    (DidiFoodScraper, "didi_raw.json"),
)


async def main() -> None:
    failures = []
    for scraper_class, output_file in SCRAPERS:
        scraper = scraper_class()
        try:
            await scraper.run(output_file)
        except Exception as exc:
            failures.append((scraper.PLATFORM_NAME, str(exc)))
        finally:
            await scraper.close()

    if failures:
        print("Scraping completed with failures:")
        for platform, error in failures:
            print(f"- {platform}: {error}")
        raise SystemExit(1)

    print("Scraping completed successfully for all platforms.")


if __name__ == "__main__":
    asyncio.run(main())
