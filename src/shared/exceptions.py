"""Custom exceptions module for the Rappi Analytics application.

This module defines application-specific exceptions for better error handling
and debugging across the ETL pipeline and API layers.
"""


class RappiAnalyticsException(Exception):
    """Base exception for all application-specific errors."""

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ScraperException(RappiAnalyticsException):
    """Exception raised during web scraping operations."""

    pass


class ScraperTimeoutException(ScraperException):
    """Exception raised when a scraping request times out."""

    pass


class ScraperBlockedException(ScraperException):
    """Exception raised when scraping is blocked by the platform."""

    pass


class ScraperLocationException(ScraperException):
    """Exception raised when location setting fails."""

    pass


class DatabaseException(RappiAnalyticsException):
    """Exception raised during database operations."""

    pass


class ValidationException(RappiAnalyticsException):
    """Exception raised during data validation."""

    pass


class TransformationException(RappiAnalyticsException):
    """Exception raised during data transformation."""

    pass


class APIException(RappiAnalyticsException):
    """Exception raised during API operations."""

    pass


class NotFoundException(APIException):
    """Exception raised when a requested resource is not found."""

    pass
