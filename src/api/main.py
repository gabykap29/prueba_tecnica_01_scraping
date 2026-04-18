"""Main FastAPI application for the Rappi Analytics API.

This module provides the main FastAPI application instance with
all routes, middleware, and configuration.
"""

from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.shared.constants import APIConstants
from .routes import (
    health_router,
    comparison_router,
    analytics_router,
    knowledge_base_router,
    ai_agent_router,
)

app = FastAPI(
    title=APIConstants.API_TITLE,
    description=APIConstants.API_DESCRIPTION,
    version=APIConstants.API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    health_router,
    prefix=APIConstants.API_PREFIX,
    tags=["health"],
)
app.include_router(
    comparison_router,
    prefix=f"{APIConstants.API_PREFIX}/analytics",
    tags=["analytics"],
)
app.include_router(
    analytics_router,
    prefix=f"{APIConstants.API_PREFIX}/analytics",
    tags=["analytics"],
)
app.include_router(
    knowledge_base_router,
    prefix=APIConstants.API_PREFIX,
    tags=["knowledge_base"],
)
app.include_router(
    ai_agent_router,
    prefix=APIConstants.API_PREFIX,
    tags=["ai-agent"],
)


@app.get("/")
def root():
    """Root endpoint for the API.

    Returns:
        Basic API information

    Example:
        >>> response = root()
        >>> response["version"]
        "1.0.0"
    """
    return {
        "message": APIConstants.API_TITLE,
        "version": APIConstants.API_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }
