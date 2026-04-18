"""Configuration module for the Rappi Analytics application.

This module provides centralized settings management using environment variables
and sensible defaults for development and production environments.

Example:
    >>> from src.shared.config import get_settings
    >>> settings = get_settings()
    >>> print(settings.DATABASE_URL)
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables.

    Attributes:
        DATABASE_URL: PostgreSQL connection string
        API_HOST: Host address for the API server
        API_PORT: Port number for the API server
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
        SCRAPER_DELAY_MIN: Minimum delay between scraper requests (seconds)
        SCRAPER_DELAY_MAX: Maximum delay between scraper requests (seconds)
        SERPAPI_API_KEY: Optional SerpApi key for Google OSINT discovery
        USER_AGENTS: List of user agent strings for web scraping
    """

    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/rappi_analytics"
        )
    )
    API_HOST: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    API_PORT: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    SCRAPER_DELAY_MIN: float = field(
        default_factory=lambda: float(os.getenv("SCRAPER_DELAY_MIN", "3.0"))
    )
    SCRAPER_DELAY_MAX: float = field(
        default_factory=lambda: float(os.getenv("SCRAPER_DELAY_MAX", "6.0"))
    )
    SERPAPI_API_KEY: str = field(
        default_factory=lambda: (
            os.getenv("SERPAPI_API_KEY", "") or os.getenv("SERAPI_API_KEY", "")
        ).strip()
    )
    USER_AGENTS: tuple = field(
        default_factory=lambda: (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        )
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings.

    This function uses functools.lru_cache to ensure settings are only
    loaded once and reused throughout the application lifecycle.

    Returns:
        Settings: Cached application settings instance

    Example:
        >>> settings = get_settings()
        >>> settings.API_PORT
        8000
    """
    return Settings()


def get_db_connection():
    """Get a database connection using the configured settings.

    Returns:
        connection: psycopg2 connection object
    """
    import psycopg2

    return psycopg2.connect(get_settings().DATABASE_URL)
