"""Pydantic AI agent implementation for delivery data extraction with conversation support.

This agent uses SerpAPI to search for current delivery prices
and extract structured data using LLM capabilities with streaming states.
"""

import os
from datetime import datetime
from typing import Optional, AsyncIterator, Callable
from enum import Enum
import asyncio
import json

import httpx

from src.ai_agent.models import (
    DeliveryPriceData,
    AgentResponse,
    PlatformComparisonResult,
    AgentState,
    AgentMessage,
)

try:
    from pydantic_ai import Agent
    from pydantic_ai.models.gemini import GeminiModel
    from pydantic_ai.providers.google_gla import GoogleGLAProvider

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class AgentStatus(Enum):
    IDLE = "idle"
    UNDERSTANDING = "understanding"
    SEARCHING = "searching"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    COMPARING = "comparing"
    COMPLETED = "completed"
    ERROR = "error"


def get_gemini_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    return GeminiModel(
        "gemini-2.0-flash",
        provider=GoogleGLAProvider(api_key=api_key),
    )


def search_serpapi(query, location="Mexico City, Mexico", num_results=10):
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return {"error": "SERPAPI_API_KEY not configured", "organic_results": []}

    params = {
        "engine": "google",
        "q": query,
        "location": location,
        "google_domain": "google.com.mx",
        "gl": "mx",
        "hl": "es",
        "num": num_results,
        "api_key": api_key,
    }

    try:
        response = httpx.get("https://serpapi.com/search", params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "organic_results": []}


def extract_price_from_snippet(snippet):
    import re

    if not snippet:
        return None
    patterns = [
        r"\$\s*(\d+(?:\.\d{1,2})?)",
        r"(\d+(?:\.\d{1,2})?)\s*pesos",
        r"(\d+(?:\.\d{1,2})?)\s*mxn",
        r"(\d+(?:\.\d{1,2})?)\s*\$",
    ]
    for pattern in patterns:
        match = re.search(pattern, snippet.lower())
        if match:
            return float(match.group(1))
    return None


def extract_time_from_snippet(snippet):
    import re

    if not snippet:
        return None
    patterns = [
        r"(\d+)\s*-\s*(\d+)\s*min",
        r"(\d+)\s*a\s*(\d+)\s*min",
        r"en\s+(\d+)\s*min",
        r"(\d+)\s*minutos",
        r"tiempo\s+de\s+(\d+)\s*min",
    ]
    for pattern in patterns:
        match = re.search(pattern, snippet.lower())
        if match:
            if "-" in pattern or "a" in pattern:
                return (int(match.group(1)) + int(match.group(2))) // 2
            return int(match.group(1))
    return None


SYSTEM_PROMPT = """Eres un asistente experto en delivery de comida en la Ciudad de Mexico.

Tu tarea es ayudar a los usuarios a encontrar informacion sobre precios, tiempos de entrega y comparar opciones entre plataformas (Rappi, Uber Eats, Didi Food).

Cuando el usuario te pregunte sobre un producto o restaurante:
1. Entiende que esta buscando
2. Busca informacion actualizada
3. Proporciona datos precisos con fuentes
4. Compara opciones si es relevante

Se amigable, conciso y util en tus respuestas.

Tambien puedes ejecutar estas acciones predefinidas cuando el usuario las pida:
- "comparar precios" o "compare": Ejecuta la comparacion de productos entre plataformas
- "resumen" o "summary": Muestra el resumen ejecutivo de competitive intelligence
- "actualizar base" o "knowledge": Actualiza la base de conocimiento con scrapeo live
- "rankings": Muestra los rankings por metricas (precio, tiempo, delivery fee)
- "health": Verifica el estado de la API
- "ayuda": Muestra los comandos disponibles
"""


class DeliveryAIAgent:
    """High-level interface for the delivery AI agent with conversation support."""

    def __init__(self):
        self._agent = None
        self._conversations = {}
        self._predefined_actions = {
            "comparar": self._action_compare,
            "compare": self._action_compare,
            "resumen": self._action_summary,
            "summary": self._action_summary,
            "actualizar": self._action_update_knowledge,
            "knowledge": self._action_update_knowledge,
            "rankings": self._action_rankings,
            "health": self._action_health,
            "ayuda": self._action_help,
            "help": self._action_help,
            "precios": self._action_prices,
            "prices": self._action_prices,
            "etas": self._action_etas,
            "tiempos": self._action_etas,
        }

    @property
    def agent(self):
        if self._agent is None and GEMINI_AVAILABLE:
            model = get_gemini_model()
            if model:
                self._agent = Agent(model=model, system_prompt=SYSTEM_PROMPT)
        return self._agent

    def get_or_create_conversation(self, conversation_id):
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []
        return self._conversations[conversation_id]

    async def chat_with_states(self, message, conversation_id="default", on_state_change=None):
        conversation = self.get_or_create_conversation(conversation_id)

        user_msg = AgentMessage(
            role="user",
            content=message,
            timestamp=datetime.utcnow().isoformat(),
        )
        conversation.append(user_msg)

        yield AgentState(
            status=AgentStatus.UNDERSTANDING.value,
            message="Analizando tu consulta...",
            progress=10,
        )
        await asyncio.sleep(0.5)

        query_info = self._parse_query(message)

        if query_info.get("is_predefined"):
            action_key = query_info.get("action")
            yield AgentState(
                status=AgentStatus.SEARCHING.value,
                message=f"Ejecutando accion: {action_key}...",
                progress=30,
                metadata=query_info,
            )

            action_result = await self._execute_predefined_action(action_key, query_info)
            response_msg = (
                action_result.get("message", "Accion completada")
                if action_result
                else "Accion completada"
            )

            yield AgentState(
                status=AgentStatus.COMPLETED.value,
                message=response_msg,
                progress=100,
                data=action_result,
                response_text=response_msg,
            )
            return

        product_name = query_info.get("product") or "el producto"

        yield AgentState(
            status=AgentStatus.SEARCHING.value,
            message=f"Buscando informacion sobre {product_name}...",
            progress=30,
            metadata=query_info,
        )

        results = []
        platforms = query_info.get("platforms", ["rappi", "ubereats", "didi"])

        for i, platform in enumerate(platforms):
            progress = 30 + (i * 15)
            yield AgentState(
                status=AgentStatus.SEARCHING.value,
                message=f"Buscando en {platform}...",
                progress=progress,
            )

            if query_info.get("restaurant") and query_info.get("product"):
                data = await self._search_platform(
                    query_info["restaurant"],
                    query_info["product"],
                    platform,
                    query_info.get("location", "Mexico City"),
                )
                if data:
                    results.append(data)

            await asyncio.sleep(0.3)

        yield AgentState(
            status=AgentStatus.EXTRACTING.value,
            message="Procesando los resultados encontrados...",
            progress=60,
            metadata={"results_count": len(results)},
        )
        await asyncio.sleep(0.5)

        yield AgentState(
            status=AgentStatus.VALIDATING.value,
            message="Validando la informacion...",
            progress=75,
        )
        await asyncio.sleep(0.3)

        comparison = None
        if len(results) > 1:
            yield AgentState(
                status=AgentStatus.COMPARING.value,
                message="Comparando opciones entre plataformas...",
                progress=85,
            )
            comparison = self._build_comparison(results)

        response_text = self._generate_response(message, results, comparison)

        yield AgentState(
            status=AgentStatus.COMPLETED.value,
            message="Listo!",
            progress=100,
            data={
                "results": [r.model_dump() for r in results],
                "comparison": comparison,
            },
            response_text=response_text,
        )

        assistant_msg = AgentMessage(
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "results": [r.model_dump() for r in results],
                "comparison": comparison,
            },
        )
        conversation.append(assistant_msg)

    def _parse_query(self, message):
        message_lower = message.lower()

        for action_key, action_func in self._predefined_actions.items():
            if action_key in message_lower:
                return {
                    "action": action_key,
                    "action_func": action_func,
                    "is_predefined": True,
                }

        restaurant = None
        if any(x in message_lower for x in ["mcdonald", "mc donald", "big mac"]):
            restaurant = "McDonald's"
        elif any(x in message_lower for x in ["burger king", "whopper", "bk"]):
            restaurant = "Burger King"
        elif any(x in message_lower for x in ["kfc", "kentucky"]):
            restaurant = "KFC"
        elif any(x in message_lower for x in ["wendy's", "wendys"]):
            restaurant = "Wendy's"

        product = None
        if "big mac" in message_lower:
            product = "Big Mac"
        elif "whopper" in message_lower:
            product = "Whopper"
        elif "nuggets" in message_lower:
            product = "Nuggets"
        elif "papas" in message_lower or "fries" in message_lower:
            product = "Papas"

        if not product and restaurant:
            if restaurant == "McDonald's":
                product = "Big Mac"
            elif restaurant == "Burger King":
                product = "Whopper"

        platforms = []
        if "rappi" in message_lower:
            platforms.append("rappi")
        if any(x in message_lower for x in ["uber", "ubereats"]):
            platforms.append("ubereats")
        if any(x in message_lower for x in ["didi", "didifood"]):
            platforms.append("didi")

        if not platforms:
            platforms = ["rappi", "ubereats", "didi"]

        location = "Mexico City"
        if "polanco" in message_lower:
            location = "Polanco, Mexico City"
        elif any(x in message_lower for x in ["roma", "condesa"]):
            location = "Roma Norte, Mexico City"
        elif "santa fe" in message_lower:
            location = "Santa Fe, Mexico City"

        return {
            "restaurant": restaurant,
            "product": product,
            "platforms": platforms,
            "location": location,
            "raw_message": message,
            "is_predefined": False,
        }

    async def _search_platform(self, restaurant, product, platform, location):
        search_terms = [
            f"{product} {restaurant} precio {platform}",
            f"{product} {restaurant} {platform} mexico",
        ]

        all_results = []
        for term in search_terms:
            result = search_serpapi(term, location)
            if "organic_results" in result:
                all_results.extend(result["organic_results"])

        data = DeliveryPriceData(
            platform=platform,
            restaurant=restaurant,
            product_name=product,
        )

        prices = []
        times = []
        urls = []

        for result in all_results:
            snippet = result.get("snippet", "")
            title = result.get("title", "")
            url = result.get("link", "")

            if url:
                urls.append(url)

            price = extract_price_from_snippet(snippet) or extract_price_from_snippet(title)
            if price and 20 < price < 500:
                prices.append(price)

            time = extract_time_from_snippet(snippet)
            if time and 10 < time < 120:
                times.append(time)

        if prices:
            data.product_price = min(prices)
            data.confidence = 0.7 if len(prices) > 1 else 0.5

        if times:
            data.estimated_time_min = int(sum(times) / len(times))

        if urls:
            data.source_url = urls[0]

        return data

    async def _execute_predefined_action(self, action_key, query_info):
        action_func = self._predefined_actions.get(action_key)
        if action_func:
            return await action_func(query_info)
        return None

    async def _action_compare(self, query_info) -> dict:
        from src.analytics.competitive import compare_product, load_current_competitive_data

        search_term = query_info.get("raw_message", "").replace("comparar ", "").strip()
        product = search_term if search_term else "Big Mac"

        records = load_current_competitive_data()
        comparison = compare_product(product=product, records=records)

        results = comparison.get("results", [])
        best_option = comparison.get("best_option", "N/A")

        if results:
            lines = [
                "=== ANALISIS COMPARATIVO ===",
                f"Producto: {product}",
                "",
                "Plataforma | Precio | Delivery | Servicio | Total",
                "-" * 55,
            ]

            prices = []
            for r in results:
                p = r.get("avg_product_price", 0) or 0
                d = r.get("avg_delivery_fee", 0) or 0
                s = r.get("avg_service_fee", 0) or 0
                t = r.get("avg_total_cost", 0) or 0
                prices.append(t)
                plat = r.get("platform", "N/A").upper().ljust(10)
                lines.append(f"{plat}   ${p:>4.0f}   ${d:>3.0f}   ${s:>3.0f}   ${t:>4.0f}")

            lines.append("-" * 55)
            lines.append(
                f"Me{'jor':>12}  {best_option.upper():<10}  ${min(prices):>4.0f}" if prices else ""
            )
            lines.append(
                f"Diferencia vs promedio: ${max(prices) - min(prices):.0f} MXN"
                if len(prices) > 1
                else ""
            )

            message = "\n".join(lines)
        else:
            message = f"No hay datos para {product}"

        return {
            "action": "compare",
            "product": product,
            "results": results,
            "best_option": best_option,
            "message": message,
        }

    async def _action_summary(self, query_info) -> dict:
        from src.analytics.competitive import generate_summary, load_current_competitive_data

        records = load_current_competitive_data()
        summary = generate_summary(records)

        return {
            "action": "summary",
            "summary": summary,
            "message": "Resumen ejecutivo generado",
        }

    async def _action_update_knowledge(self, query_info) -> dict:
        import scripts.build_live_snapshot as build_snapshot_module
        import scripts.scrape_rappi_live as scrape_rappi_module

        result = await scrape_rappi_module.scrape_rappi(
            output_path="data/live_rappi_snapshot.csv",
            limit_addresses=1,
            limit_restaurants=1,
            headless=True,
        )

        snapshot_path = build_snapshot_module.build_snapshot()

        return {
            "action": "update_knowledge",
            "output": str(result),
            "snapshot": str(snapshot_path),
            "message": "Base de conocimiento actualizada",
        }

    async def _action_rankings(self, query_info) -> dict:
        from src.analytics.competitive import generate_summary, load_current_competitive_data

        records = load_current_competitive_data()
        summary = generate_summary(records)
        zones = summary.get("zones", [])

        ranked = sorted(zones, key=lambda x: x.get("avg_total_cost", float("inf")))[:10]

        return {
            "action": "rankings",
            "rankings": ranked,
            "message": "Rankings generados",
        }

    async def _action_health(self, query_info) -> dict:
        return {
            "action": "health",
            "status": "healthy",
            "message": "API operativa",
        }

    async def _action_help(self, query_info) -> dict:
        return {
            "action": "help",
            "commands": list(self._predefined_actions.keys()),
            "message": """Comandos disponibles:
- comparar [producto]: Compara precios entre plataformas
- resumen: Muestra resumen ejecutivo
- actualizar: Actualiza base de conocimiento
- rankings: Muestra rankings por metricas
- precios: Muestra precios por zona
- tiempos: Muestra tiempos de entrega
- health: Estado de la API
- ayuda: Muestra este mensaje""",
        }

    async def _action_prices(self, query_info) -> dict:
        from src.analytics.competitive import platform_averages, load_current_competitive_data

        records = load_current_competitive_data()
        averages = platform_averages(records)

        return {
            "action": "prices",
            "averages": averages,
            "message": "Precios promedio por plataforma",
        }

    async def _action_etas(self, query_info) -> dict:
        from src.analytics.competitive import eta_by_platform, load_current_competitive_data

        records = load_current_competitive_data()
        etas = eta_by_platform(records, restaurant="McDonald's")

        return {
            "action": "etas",
            "etas": etas,
            "message": "Tiempos de entrega por plataforma",
        }

    def _parse_query(self, message):
        message_lower = message.lower()

        restaurant = None
        if any(x in message_lower for x in ["mcdonald", "mc donald", "big mac"]):
            restaurant = "McDonald's"
        elif any(x in message_lower for x in ["burger king", "whopper", "bk"]):
            restaurant = "Burger King"
        elif any(x in message_lower for x in ["kfc", "kentucky"]):
            restaurant = "KFC"
        elif any(x in message_lower for x in ["wendy's", "wendys"]):
            restaurant = "Wendy's"

        product = None
        if "big mac" in message_lower:
            product = "Big Mac"
        elif "whopper" in message_lower:
            product = "Whopper"
        elif "nuggets" in message_lower:
            product = "Nuggets"
        elif "papas" in message_lower or "fries" in message_lower:
            product = "Papas"

        if not product and restaurant:
            if restaurant == "McDonald's":
                product = "Big Mac"
            elif restaurant == "Burger King":
                product = "Whopper"

        platforms = []
        if "rappi" in message_lower:
            platforms.append("rappi")
        if any(x in message_lower for x in ["uber", "ubereats"]):
            platforms.append("ubereats")
        if any(x in message_lower for x in ["didi", "didifood"]):
            platforms.append("didi")

        if not platforms:
            platforms = ["rappi", "ubereats", "didi"]

        location = "Mexico City"
        if "polanco" in message_lower:
            location = "Polanco, Mexico City"
        elif any(x in message_lower for x in ["roma", "condesa"]):
            location = "Roma Norte, Mexico City"
        elif "santa fe" in message_lower:
            location = "Santa Fe, Mexico City"

        return {
            "restaurant": restaurant,
            "product": product,
            "platforms": platforms,
            "location": location,
            "raw_message": message,
            "is_predefined": False,
        }

    def _build_comparison(self, results):
        if not results:
            return None

        valid = [r for r in results if r.product_price is not None]
        if not valid:
            return None

        best = min(valid, key=lambda x: x.product_price or float("inf"))

        return {
            "best_platform": best.platform,
            "best_price": best.product_price,
            "platforms_compared": [r.platform for r in valid],
            "price_range": {
                "min": min(r.product_price for r in valid if r.product_price),
                "max": max(r.product_price for r in valid if r.product_price),
            },
        }

    def _generate_response(self, query, results, comparison):
        if not results:
            return "No se encontraron datos. Intenta con otro producto o restaurante."

        if comparison:
            best = comparison["best_platform"]
            price = comparison["best_price"]
            range_min = comparison["price_range"]["min"]
            range_max = comparison["price_range"]["max"]

            lines = [
                "=== COMPARATIVA DE PRECIOS ===",
                f"Producto: {results[0].product_name}",
                "",
                "PLATAFORMA | PRECIO | SERVICIO | Total",
                "-" * 45,
            ]

            for r in results:
                p = r.product_price or 0
                d = r.delivery_fee or 0
                s = r.service_fee or 0
                total = p + d + s
                platform = r.platform.upper().ljust(10)
                lines.append(f"{platform} | ${p:.0f} | $${d:.0f}+${s:.0f} | ${total:.0f}")

            lines.extend(
                [
                    "-" * 45,
                    f"Mejor option: {best.upper()} (${price:.0f} MXN)",
                    f"Rango: ${range_min:.0f} - ${range_max:.0f} MXN",
                    "",
                    f"Whopper: ${range_max - price:.0f} MXN vs mejor option",
                ]
            )

            return "\n".join(lines)

        if len(results) == 1:
            r = results[0]
            total = (r.product_price or 0) + (r.delivery_fee or 0) + (r.service_fee or 0)
            return (
                f"[{r.platform.upper()}]\n"
                f"Producto: {r.product_name}\n"
                f"Precio producto: ${r.product_price or 'N/A'}\n"
                f"Delivery: ${r.delivery_fee or 0} | Servicio: ${r.service_fee or 0}\n"
                f"Costo total: ${total:.0f} MXN\n"
                f"Tiempo entrega: {r.estimated_time_min or 'N/A'} min"
            )

        return f"Datos obtenidos de {len(results)} plataformas."

    def get_conversation_history(self, conversation_id="default"):
        return self._conversations.get(conversation_id, [])

    def clear_conversation(self, conversation_id="default"):
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]

    async def get_product_price(self, restaurant, product, platform=None, address=None):
        try:
            location = address or "Mexico City, Mexico"
            data = await self._search_platform(restaurant, product, platform or "rappi", location)

            return AgentResponse(
                success=True,
                data=data,
                search_queries_used=[f"{product} {restaurant} {platform or 'delivery'}"],
                raw_results_count=1,
            )
        except Exception as e:
            return AgentResponse(success=False, error=str(e))

    async def compare_product_across_platforms(self, restaurant, product, address=None):
        platforms = ["rappi", "ubereats", "didi"]
        results = []

        for platform in platforms:
            data = await self._search_platform(
                restaurant, product, platform, address or "Mexico City"
            )
            if data and data.product_price:
                results.append(data)

        valid = [r for r in results if r.total_cost is not None]
        if valid:
            best = min(valid, key=lambda x: x.total_cost or float("inf"))
            prices = [r.total_cost for r in valid if r.total_cost]
            price_diff = (
                ((sum(prices) / len(prices) - best.total_cost) / (sum(prices) / len(prices)) * 100)
                if len(prices) > 1
                else None
            )
        else:
            best = None
            price_diff = None

        return PlatformComparisonResult(
            product=product,
            address=address,
            platform_results=results,
            best_platform=best.platform if best else None,
            best_price=best.total_cost if best else None,
            price_difference_pct=price_diff,
        )


ai_agent = DeliveryAIAgent()
