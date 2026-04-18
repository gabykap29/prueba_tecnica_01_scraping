"""API routes for the Rappi Analytics application.

This module provides FastAPI route handlers for the API endpoints.
"""

from src.api.routes.health import router as health_router
from src.api.routes.comparison import router as comparison_router
from src.api.routes.analytics import router as analytics_router
from src.api.routes.knowledge_base import router as knowledge_base_router
from src.ai_agent.router import router as ai_agent_router

__all__ = [
    "health_router",
    "comparison_router",
    "analytics_router",
    "knowledge_base_router",
    "ai_agent_router",
]
