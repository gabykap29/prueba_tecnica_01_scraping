"""Knowledge base update routes for the Rappi Analytics API."""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

import scripts.scrape_rappi_live as scrape_rappi_module
import scripts.scrape_ubereats_live as scrape_ubereats_module
import scripts.scrape_didi_live as scrape_didi_module
import scripts.build_live_snapshot as build_snapshot_module
from src.analytics.competitive import load_current_competitive_data, live_scrape_status
from src.shared.config import get_db_connection

router = APIRouter()

logger = logging.getLogger(__name__)


def clear_database() -> dict:
    """Clear warehouse tables when Postgres is available."""
    tables = ["raw_scrape", "price_analytics"]
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for table in tables:
            cur.execute(f"DELETE FROM {table}")
        conn.commit()
        logger.info("Database cleared successfully")
        return {"status": "success", "tables": tables}
    except Exception as e:
        logger.warning(
            "Skipping database cleanup because Postgres is unavailable or misconfigured: %s",
            e,
        )
        return {"status": "skipped", "error": str(e)}
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()


async def run_all_scrapers():
    """Run all platform scrapers and build the merged snapshot."""
    results = [{"platform": "database", **clear_database()}]

    scrapers = [
        ("rappi", "data/live_rappi_snapshot.csv", scrape_rappi_module.scrape_rappi),
        ("ubereats", "data/live_ubereats_snapshot.csv", scrape_ubereats_module.scrape_ubereats),
        ("didi", "data/live_didi_snapshot.csv", scrape_didi_module.scrape_didi),
    ]

    for platform, output_path, scraper_func in scrapers:
        try:
            result = await scraper_func(
                output_path=output_path,
                limit_addresses=1,
                limit_restaurants=1,
                headless=True,
            )
            results.append(
                {
                    "platform": platform,
                    "status": "success",
                    "output": str(result),
                }
            )
        except Exception as e:
            logger.error(f"Scraper failed for {platform}: {e}")
            results.append(
                {
                    "platform": platform,
                    "status": "failed",
                    "error": str(e),
                }
            )

    try:
        snapshot_path = build_snapshot_module.build_snapshot()
        results.append(
            {
                "platform": "merged",
                "status": "success",
                "output": str(snapshot_path),
            }
        )
    except Exception as e:
        logger.error(f"Build snapshot failed: {e}")
        results.append(
            {
                "platform": "merged",
                "status": "failed",
                "error": str(e),
            }
        )

    return results


@router.post("/update-knowledge")
async def update_knowledge_base(background_tasks: BackgroundTasks):
    """Update the knowledge base by running all scrapers and building the snapshot.

    This endpoint triggers a background task to scrape data from all platforms
    (Rappi, UberEats, DiDi) and builds the merged CSV file used
    for analytics.

    Returns:
        Status of the update operation

    Example:
        >>> response = update_knowledge_base()
        >>> response["status"]
        "started"
    """
    background_tasks.add_task(run_all_scrapers)

    return {
        "status": "started",
        "message": "Knowledge base update initiated in background",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/update-knowledge/status")
async def get_update_status():
    """Get the current knowledge base status.

    Returns:
        Status information including last scrape results

    Example:
        >>> response = get_update_status()
        >>> response["records"]
        150
    """
    try:
        records = load_current_competitive_data()
    except FileNotFoundError:
        records = []

    statuses = live_scrape_status()

    return {
        "status": "ready" if records else "empty",
        "records": len(records),
        "scrape_status": statuses,
        "timestamp": datetime.utcnow().isoformat(),
    }
