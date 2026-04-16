"""Health check routes for the Rappi Analytics API.

This module provides health and readiness endpoints
for monitoring the API service status.
"""

from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    """Check if the API is healthy.

    Returns:
        Health status with timestamp

    Example:
        >>> response = health_check()
        >>> response["status"]
        "healthy"
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "rappi-analytics",
    }


@router.get("/ready")
def readiness_check():
    """Check if the API is ready to serve requests.

    Returns:
        Readiness status with timestamp

    Example:
        >>> response = readiness_check()
        >>> response["status"]
        "ready"
    """
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
    }
