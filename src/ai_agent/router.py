"""API routes for the AI Agent with conversation support.

Provides endpoints for AI-powered delivery data extraction
with streaming states and conversation history.
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.ai_agent.agent import ai_agent
from src.ai_agent.models import (
    DeliveryPriceData,
    AgentResponse,
    PlatformComparisonResult,
    ChatRequest,
    AgentState,
)

router = APIRouter(prefix="/ai-agent", tags=["ai-agent"])


class ChatMessageRequest(BaseModel):
    """Simple chat message request."""
    message: str
    conversation_id: Optional[str] = "default"


@router.post("/chat")
async def chat(request: ChatMessageRequest) -> dict:
    """Simple chat endpoint without streaming.
    
    Args:
        message: User message
        conversation_id: Optional conversation ID for context
        
    Returns:
        Final response after processing all states
    """
    states = []
    async for state in ai_agent.chat_with_states(
        message=request.message,
        conversation_id=request.conversation_id,
    ):
        states.append(state)
    
    if not states:
        raise HTTPException(status_code=500, detail="No response from agent")
    
    final_state = states[-1]
    
    return {
        "conversation_id": request.conversation_id,
        "response": final_state.response_text,
        "data": final_state.data,
        "states": [s.model_dump() for s in states],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatMessageRequest):
    """Chat endpoint with Server-Sent Events streaming.
    
    Streams AgentState objects as the agent processes the request:
    - understanding: Analizando tu consulta...
    - searching: Buscando en [platform]...
    - extracting: Procesando resultados...
    - validating: Validando informacion...
    - comparing: Comparando opciones...
    - completed: Listo!
    
    Example usage with JavaScript:
    ```javascript
    const eventSource = new EventSource('/api/v1/ai-agent/chat/stream?message=Big Mac');
    eventSource.onmessage = (event) => {
        const state = JSON.parse(event.data);
        console.log(state.status, state.message, state.progress + '%');
    };
    ```
    """
    async def generate_states():
        async for state in ai_agent.chat_with_states(
            message=request.message,
            conversation_id=request.conversation_id,
        ):
            yield f"data: {json.dumps(state.model_dump(), ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_states(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/stream")
async def chat_stream_get(
    message: str = Query(..., description="User message"),
    conversation_id: str = Query(default="default", description="Conversation ID"),
):
    """Chat streaming via GET request (for easier testing in browser).
    
    Usage: /api/v1/ai-agent/chat/stream?message=Big%20Mac
    """
    async def generate_states():
        async for state in ai_agent.chat_with_states(
            message=message,
            conversation_id=conversation_id,
        ):
            yield f"data: {json.dumps(state.model_dump(), ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_states(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict:
    """Get conversation history."""
    messages = ai_agent.get_conversation_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": [msg.model_dump() for msg in messages],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.delete("/conversations/{conversation_id}")
async def clear_conversation(conversation_id: str) -> dict:
    """Clear conversation history."""
    ai_agent.clear_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "status": "cleared",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/search")
async def search_product(
    restaurant: str = Query(..., description="Restaurant name (e.g., McDonald's)"),
    product: str = Query(..., description="Product name (e.g., Big Mac)"),
    platform: Optional[str] = Query(None, description="Platform: rappi, ubereats, didi"),
    address: Optional[str] = Query(None, description="Delivery address in CDMX"),
) -> dict:
    """Search for product pricing using AI agent with SerpAPI."""
    result = await ai_agent.get_product_price(
        restaurant=restaurant,
        product=product,
        platform=platform,
        address=address,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "success": True,
        "data": result.data.model_dump() if result.data else None,
        "search_queries_used": result.search_queries_used,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/compare")
async def compare_product(
    restaurant: str = Query(..., description="Restaurant name"),
    product: str = Query(..., description="Product name"),
    address: Optional[str] = Query(None, description="Delivery address in CDMX"),
) -> dict:
    """Compare product prices across all platforms using AI."""
    result = await ai_agent.compare_product_across_platforms(
        restaurant=restaurant,
        product=product,
        address=address,
    )

    return {
        "product": result.product,
        "address": result.address,
        "platform_results": [r.model_dump() for r in result.platform_results],
        "best_platform": result.best_platform,
        "best_price": result.best_price,
        "price_difference_pct": result.price_difference_pct,
        "generated_at": result.generated_at,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/health")
async def health_check() -> dict:
    """Check AI agent health status."""
    import os

    has_serpapi_key = bool(os.getenv("SERPAPI_API_KEY"))
    has_gemini_key = bool(os.getenv("GEMINI_API_KEY"))

    return {
        "status": "healthy" if has_serpapi_key else "degraded",
        "serpapi_configured": has_serpapi_key,
        "gemini_configured": has_gemini_key,
        "model": "gemini-2.0-flash",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/platforms")
async def get_supported_platforms() -> list[str]:
    """Get list of supported platforms."""
    return ["rappi", "ubereats", "didi"]


@router.get("/quick-compare/{product_name}")
async def quick_compare(
    product_name: str,
    restaurant: Optional[str] = Query(None, description="Optional restaurant filter"),
) -> dict:
    """Quick comparison using AI agent with auto-detected restaurant."""
    product_lower = product_name.lower()
    detected_restaurant = restaurant
    if not detected_restaurant:
        if "big mac" in product_lower or "mc" in product_lower:
            detected_restaurant = "McDonald's"
        elif "whopper" in product_lower or "burger king" in product_lower:
            detected_restaurant = "Burger King"
        else:
            detected_restaurant = "McDonald's"

    result = await ai_agent.compare_product_across_platforms(
        restaurant=detected_restaurant,
        product=product_name,
    )

    return {
        "product": result.product,
        "restaurant": detected_restaurant,
        "best_platform": result.best_platform,
        "best_price": result.best_price,
        "platform_results": [r.model_dump() for r in result.platform_results],
        "timestamp": datetime.utcnow().isoformat(),
    }
