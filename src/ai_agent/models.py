"""Pydantic AI agent for delivery data extraction.

This module provides models for structured data and conversation states.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, field_validator


class DeliveryPriceData(BaseModel):
    """Structured output for delivery price extraction."""

    platform: str = Field(description="Platform name: rappi, ubereats, or didi")
    restaurant: str = Field(description="Restaurant name (e.g., McDonald's, Burger King)")
    product_name: str = Field(description="Product name (e.g., Big Mac, Whopper)")
    product_price: Optional[float] = Field(None, description="Product price in MXN")
    delivery_fee: Optional[float] = Field(None, description="Delivery fee in MXN")
    service_fee: Optional[float] = Field(None, description="Service fee in MXN")
    estimated_time_min: Optional[int] = Field(None, description="Estimated delivery time in minutes")
    active_promo: Optional[str] = Field(None, description="Active promotion if any")
    total_cost: Optional[float] = Field(None, description="Total cost including all fees")
    scraped_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source_url: Optional[str] = Field(None, description="Source URL where data was found")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score (0-1)")

    @field_validator("product_price", "delivery_fee", "service_fee", mode="before")
    @classmethod
    def parse_price(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").replace("MXN", "").strip()
            return float(cleaned) if cleaned else None
        return float(v)

    @field_validator("total_cost", mode="before")
    @classmethod
    def calculate_total(cls, v, info):
        if v is not None:
            return v
        values = info.data
        prices = [
            values.get("product_price"),
            values.get("delivery_fee"),
            values.get("service_fee"),
        ]
        valid_prices = [p for p in prices if p is not None]
        return sum(valid_prices) if valid_prices else None


class PlatformComparisonResult(BaseModel):
    """Result comparing a product across platforms."""

    product: str
    zone_type: Optional[str] = None
    address: Optional[str] = None
    platform_results: list[DeliveryPriceData] = Field(default_factory=list)
    best_platform: Optional[str] = None
    best_price: Optional[float] = None
    price_difference_pct: Optional[float] = None
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SearchQuery(BaseModel):
    """Search query for the agent."""

    restaurant: str
    product: str
    address: Optional[str] = None
    platform: Optional[str] = None


class AgentResponse(BaseModel):
    """Response from the AI agent."""

    success: bool
    data: Optional[DeliveryPriceData] = None
    error: Optional[str] = None
    search_queries_used: list[str] = Field(default_factory=list)
    raw_results_count: int = 0


class AgentState(BaseModel):
    """State of the agent during processing with streaming updates."""

    status: str = Field(..., description="Current status: understanding, searching, extracting, validating, comparing, completed, error")
    message: str = Field(..., description="Human-readable message about current state")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage (0-100)")
    data: Optional[dict] = Field(None, description="Partial or final results")
    metadata: Optional[dict] = Field(None, description="Additional metadata about current state")
    response_text: Optional[str] = Field(None, description="Final response text when completed")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentMessage(BaseModel):
    """A single message in the conversation."""

    role: str = Field(..., description="Role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Optional[dict] = Field(None, description="Additional metadata")


class ChatRequest(BaseModel):
    """Request for chat endpoint."""

    message: str = Field(..., description="User message")
    conversation_id: Optional[str] = Field(default="default", description="Conversation ID for maintaining context")
    stream: bool = Field(default=True, description="Whether to stream states")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    conversation_id: str
    messages: list[AgentMessage]
    final_state: Optional[AgentState] = None
