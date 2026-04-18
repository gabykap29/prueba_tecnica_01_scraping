"""Pydantic AI agent implementation for delivery data extraction with conversation support.

This agent uses SerpAPI to search for current delivery prices
and extract structured data using LLM capabilities with streaming states.
"""

import os
from datetime import datetime
from typing import Optional
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
    api_key = os.getenv("SERPAPI_API_KEY") or os.getenv("SERAPI_API_KEY")
    if not api_key:
        return {"error": "SERPAPI_API_KEY/SERAPI_API_KEY not configured", "organic_results": []}

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
            "tendencias": self._action_trends,
            "trends": self._action_trends,
            "snapshot": self._action_trends,
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

    async def chat_once(self, message, conversation_id="default"):
        states = []
        async for state in self.chat_with_states(message, conversation_id):
            states.append(state)
        if not states:
            return {
                "conversation_id": conversation_id,
                "response": "No se obtuvo respuesta del agente",
                "data": None,
                "states": [],
                "timestamp": datetime.utcnow().isoformat(),
            }
        final_state = states[-1]
        return {
            "conversation_id": conversation_id,
            "response": final_state.response_text or final_state.message,
            "data": final_state.data,
            "states": [state.model_dump() for state in states],
            "timestamp": datetime.utcnow().isoformat(),
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

    def _default_restaurant_product(self, query_info):
        restaurant = query_info.get("restaurant")
        product = query_info.get("product")

        if not restaurant and product == "Whopper":
            restaurant = "Burger King"
        elif not restaurant:
            restaurant = "McDonald's"

        if not product and restaurant == "Burger King":
            product = "Whopper"
        elif not product:
            product = "Big Mac"

        return restaurant, product

    def _has_live_signal(self, data: DeliveryPriceData) -> bool:
        return any(
            value is not None
            for value in [
                data.product_price,
                data.delivery_fee,
                data.service_fee,
                data.total_cost,
                data.estimated_time_min,
            ]
        )

    def _agent_row(self, data: DeliveryPriceData) -> dict:
        total = data.total_cost
        if total is None:
            parts = [data.product_price, data.delivery_fee, data.service_fee]
            valid_parts = [part for part in parts if part is not None]
            total = sum(valid_parts) if valid_parts else None

        return {
            "platform": data.platform,
            "restaurant": data.restaurant,
            "product": data.product_name,
            "avg_product_price": data.product_price,
            "avg_delivery_fee": data.delivery_fee,
            "avg_service_fee": data.service_fee,
            "avg_total_cost": total,
            "avg_eta_min": data.estimated_time_min,
            "source_url": data.source_url,
            "confidence": data.confidence,
            "scraped_at": data.scraped_at,
            "live_records": 1 if self._has_live_signal(data) else 0,
            "backup_records": 0,
            "error_records": 0 if self._has_live_signal(data) else 1,
            "records": 1,
        }

    async def _collect_live_rows(self, query_info, restaurant=None, product=None) -> list[dict]:
        restaurant = restaurant or query_info.get("restaurant")
        product = product or query_info.get("product")
        location = query_info.get("location", "Mexico City")
        platforms = query_info.get("platforms") or ["rappi", "ubereats", "didi"]

        rows = []
        for platform in platforms:
            data = await self._search_platform(restaurant, product, platform, location)
            if data and self._has_live_signal(data):
                rows.append(self._agent_row(data))
        return rows

    def _no_live_data_response(self, action, query_info, product=None, restaurant=None) -> dict:
        product = product or query_info.get("product") or "el producto solicitado"
        restaurant = restaurant or query_info.get("restaurant") or "el restaurante solicitado"
        message = (
            "No pude obtener informacion actualizada desde SerpApi/agente para "
            f"{product} en {restaurant}. No voy a inventar datos ni responder con el CSV local."
        )
        return {
            "action": action,
            "source_type": "live_agent",
            "fallback_used": False,
            "product": product,
            "restaurant": restaurant,
            "results": [],
            "rankings": [],
            "sources": [],
            "source_urls": [],
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _fmt_number(self, value) -> str:
        if value is None:
            return "N/A"
        return f"{value:.0f}"

    def _platform_position(self, rows, platform, value_key):
        ranked = [
            row for row in rows if row.get(value_key) is not None
        ]
        ranked.sort(key=lambda row: row[value_key])
        for index, row in enumerate(ranked, start=1):
            if row.get("platform") == platform:
                return index
        return "no_data"

    def _savings_vs_average(self, rows, best):
        if not best or best.get("avg_total_cost") is None:
            return 0
        costs = [row.get("avg_total_cost") for row in rows if row.get("avg_total_cost") is not None]
        if not costs:
            return 0
        return round((sum(costs) / len(costs)) - best["avg_total_cost"], 2)

    def _average_rows_by_platform(self, rows):
        grouped = {}
        for row in rows:
            platform = row.get("platform") or "unknown"
            grouped.setdefault(platform, []).append(row)

        averages = []
        for platform, platform_rows in grouped.items():
            average_row = {
                "platform": platform,
                "records": len(platform_rows),
                "live_records": len(platform_rows),
                "backup_records": 0,
                "error_records": 0,
            }
            for key in [
                "avg_product_price",
                "avg_delivery_fee",
                "avg_service_fee",
                "avg_total_cost",
                "avg_eta_min",
            ]:
                values = [
                    row.get(key)
                    for row in platform_rows
                    if row.get(key) is not None
                ]
                average_row[key] = round(sum(values) / len(values), 2) if values else None
            averages.append(average_row)

        return sorted(
            averages,
            key=lambda row: row.get("avg_total_cost")
            if row.get("avg_total_cost") is not None
            else float("inf"),
        )

    def _live_summary_insights(self, platform_averages):
        insights = []
        costs = [row for row in platform_averages if row.get("avg_total_cost") is not None]
        if costs:
            best_cost = min(costs, key=lambda row: row["avg_total_cost"])
            insights.append(
                f"{best_cost['platform']} aparece como la opcion live mas barata "
                f"(${best_cost['avg_total_cost']:.0f} MXN promedio)."
            )

        etas = [row for row in platform_averages if row.get("avg_eta_min") is not None]
        if etas:
            best_eta = min(etas, key=lambda row: row["avg_eta_min"])
            insights.append(
                f"{best_eta['platform']} muestra el ETA live mas bajo "
                f"({best_eta['avg_eta_min']:.0f} min promedio)."
            )

        delivery_fees = [
            row for row in platform_averages if row.get("avg_delivery_fee") is not None
        ]
        if delivery_fees:
            best_delivery = min(delivery_fees, key=lambda row: row["avg_delivery_fee"])
            insights.append(
                f"{best_delivery['platform']} tiene el delivery fee live mas bajo "
                f"(${best_delivery['avg_delivery_fee']:.0f} MXN promedio)."
            )

        if len(costs) > 1:
            spread = max(row["avg_total_cost"] for row in costs) - min(
                row["avg_total_cost"] for row in costs
            )
            insights.append(f"La dispersion live entre plataformas es de ${spread:.0f} MXN.")

        insights.append("Fuente: busqueda OSINT via SerpApi procesada por el agente.")
        return insights[:5]

    def _sources_from_rows(self, rows):
        sources = []
        seen = set()
        for row in rows:
            url = row.get("source_url")
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "platform": row.get("platform"),
                    "restaurant": row.get("restaurant"),
                    "product": row.get("product"),
                    "url": url,
                    "source_url": url,
                    "confidence": row.get("confidence"),
                    "scraped_at": row.get("scraped_at"),
                }
            )
        return sources

    def _metric_label(self, metric):
        return {
            "price": "costo total",
            "eta": "tiempo estimado de entrega",
            "delivery_fee": "costo de envio",
            "service_fee": "tarifa de servicio",
        }.get(metric, metric or "metrica")

    def _explain_platform_rows(self, title, rows, value_key="avg_total_cost"):
        lines = [f"**{title}**"]
        if not rows:
            lines.append("No encontre senales live suficientes para explicar este resultado.")
            return "\n\n".join(lines)

        metric_by_key = {
            "avg_total_cost": "price",
            "avg_delivery_fee": "delivery_fee",
            "avg_service_fee": "service_fee",
            "avg_eta_min": "eta",
        }
        metric = metric_by_key.get(value_key, "price")
        suffix = "min" if metric == "eta" else "MXN"
        prefix = "" if metric == "eta" else "$"

        ranked = [row for row in rows if row.get(value_key) is not None]
        ranked.sort(key=lambda row: row[value_key])

        if ranked:
            best = ranked[0]
            lines.append(
                f"La mejor senal live aparece en **{best.get('platform', 'N/A')}** "
                f"con {self._metric_label(metric)} de "
                f"**{prefix}{best[value_key]:.0f} {suffix}**."
            )
            if len(ranked) > 1:
                worst = ranked[-1]
                spread = worst[value_key] - best[value_key]
                lines.append(
                    f"La diferencia contra la opcion mas alta es de "
                    f"**{prefix}{spread:.0f} {suffix}** "
                    f"frente a **{worst.get('platform', 'N/A')}**."
                )

        eta_rows = [row for row in rows if row.get("avg_eta_min") is not None]
        if eta_rows:
            fastest = min(eta_rows, key=lambda row: row["avg_eta_min"])
            lines.append(
                f"En tiempo, la mejor senal es **{fastest.get('platform', 'N/A')}** "
                f"con aproximadamente **{fastest['avg_eta_min']:.0f} min**."
            )

        source_count = len([row for row in rows if row.get("source_url")])
        lines.append(
            f"Use busqueda OSINT con SerpApi y encontre {len(rows)} senales utiles "
            f"({source_count} con URL fuente). El grafico resume esos mismos datos."
        )
        return "\n\n".join(lines)

    def _explain_rankings(self, ranked, metric):
        lines = [f"**Ranking live por {self._metric_label(metric)}**"]
        if not ranked:
            lines.append("No encontre senales suficientes para ordenar plataformas.")
            return "\n\n".join(lines)

        suffix = "min" if metric == "eta" else "MXN"
        prefix = "" if metric == "eta" else "$"

        winner = ranked[0]
        lines.append(
            f"El primer lugar es **{winner.get('platform', 'N/A')}** para "
            f"**{winner.get('product', 'producto')}** con valor "
            f"**{prefix}{self._fmt_number(winner.get('metric_value'))} {suffix}**."
        )

        if len(ranked) > 1:
            runner_up = ranked[1]
            lines.append(
                f"Le sigue **{runner_up.get('platform', 'N/A')}** para "
                f"**{runner_up.get('product', 'producto')}** con "
                f"**{prefix}{self._fmt_number(runner_up.get('metric_value'))} {suffix}**. "
                "La tabla y el grafico muestran el orden completo."
            )

        lines.append(
            "Estos rankings vienen del agente live, no del CSV local; si una plataforma "
            "no aparece, fue porque no hubo senal confiable para esa metrica."
        )
        return "\n\n".join(lines)

    async def _action_compare(self, query_info) -> dict:
        restaurant, product = self._default_restaurant_product(query_info)
        rows = await self._collect_live_rows(query_info, restaurant, product)

        if not rows:
            return self._no_live_data_response("compare", query_info, product, restaurant)

        valid_costs = [row for row in rows if row.get("avg_total_cost") is not None]
        best = min(valid_costs, key=lambda row: row["avg_total_cost"]) if valid_costs else None
        best_option = best.get("platform") if best else None
        prices = [row["avg_total_cost"] for row in valid_costs]

        lines = [
            self._explain_platform_rows(
                f"Analisis live para {product} en {restaurant}",
                rows,
                "avg_total_cost",
            ),
            "",
            "**Detalle encontrado**",
            "",
            "Plataforma | Producto | Delivery | Servicio | Total | ETA",
            "--- | ---: | ---: | ---: | ---: | ---:",
        ]
        for row in rows:
            lines.append(
                "{platform} | ${product_price} | ${delivery} | "
                "${service} | ${total} | {eta} min".format(
                    platform=(row.get("platform") or "N/A").upper(),
                    product_price=self._fmt_number(row.get("avg_product_price")),
                    delivery=self._fmt_number(row.get("avg_delivery_fee")),
                    service=self._fmt_number(row.get("avg_service_fee")),
                    total=self._fmt_number(row.get("avg_total_cost")),
                    eta=row.get("avg_eta_min") or "N/A",
                )
            )

        if best:
            lines.append(
                f"\n**Mejor opcion live:** {best_option.upper()} "
                f"(${best['avg_total_cost']:.0f} MXN)"
            )
        if len(prices) > 1:
            lines.append(f"Diferencia live: ${max(prices) - min(prices):.0f} MXN")

        return {
            "action": "compare",
            "source_type": "live_agent",
            "fallback_used": False,
            "product": product,
            "restaurant": restaurant,
            "zone": query_info.get("zone") or "all",
            "results": rows,
            "sources": self._sources_from_rows(rows),
            "source_urls": self._sources_from_rows(rows),
            "best_option": best_option or "no_data",
            "rappi_position": self._platform_position(rows, "rappi", "avg_total_cost"),
            "savings_vs_avg": self._savings_vs_average(rows, best),
            "plotly": self._plotly_platform_bars(
                "Costo total live por plataforma",
                rows,
                "avg_total_cost",
                "Costo total MXN",
            ),
            "message": "\n".join(lines),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _action_summary(self, query_info) -> dict:
        products = [
            ("McDonald's", "Big Mac"),
            ("Burger King", "Whopper"),
        ]
        rows = []
        for restaurant, product in products:
            rows.extend(await self._collect_live_rows(query_info, restaurant, product))

        if not rows:
            return self._no_live_data_response("summary", query_info)

        platform_averages = self._average_rows_by_platform(rows)
        top_insights = self._live_summary_insights(platform_averages)
        summary = {
            "records": len(rows),
            "platform_averages": platform_averages,
            "zones": [],
            "top_insights": top_insights,
            "source_urls": self._sources_from_rows(rows),
        }

        return {
            "action": "summary",
            "source_type": "live_agent",
            "fallback_used": False,
            "summary": summary,
            **summary,
            "sources": self._sources_from_rows(rows),
            "plotly": {
                "platform_costs": self._plotly_platform_bars(
                    "Costo total live promedio",
                    platform_averages,
                    "avg_total_cost",
                    "Costo total MXN",
                ),
                "eta": self._plotly_platform_bars(
                    "ETA live promedio",
                    platform_averages,
                    "avg_eta_min",
                    "Minutos",
                ),
            },
            "message": "\n\n".join(
                [
                    "**Resumen ejecutivo live**",
                    *top_insights,
                    "El grafico compara el costo total y el ETA promedio por plataforma con las senales encontradas por el agente.",
                ]
            ),
            "timestamp": datetime.utcnow().isoformat(),
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
        metric = query_info.get("metric") or "price"
        metric_key = {
            "price": "avg_total_cost",
            "eta": "avg_eta_min",
            "delivery_fee": "avg_delivery_fee",
            "service_fee": "avg_service_fee",
        }.get(metric, "avg_total_cost")

        products = [
            ("McDonald's", "Big Mac"),
            ("Burger King", "Whopper"),
        ]
        rows = []
        for restaurant, product in products:
            rows.extend(await self._collect_live_rows(query_info, restaurant, product))

        ranked_rows = [
            row for row in rows if row.get(metric_key) is not None
        ]
        ranked_rows = sorted(ranked_rows, key=lambda row: row.get(metric_key, float("inf")))[:10]

        if not ranked_rows:
            response = self._no_live_data_response("rankings", query_info)
            response.update({"metric": metric, "limit": 10})
            return response

        ranked = [
            {
                "rank": index + 1,
                "platform": row.get("platform"),
                "zone_type": query_info.get("zone") or "live",
                "metric_value": row.get(metric_key, 0),
                **row,
            }
            for index, row in enumerate(ranked_rows)
        ]

        return {
            "action": "rankings",
            "source_type": "live_agent",
            "fallback_used": False,
            "metric": metric,
            "zone_type": query_info.get("zone") or "all",
            "limit": 10,
            "rankings": ranked,
            "sources": self._sources_from_rows(ranked),
            "source_urls": self._sources_from_rows(ranked),
            "plotly": self._plotly_rankings(ranked, "metric_value"),
            "message": self._explain_rankings(ranked, metric),
            "timestamp": datetime.utcnow().isoformat(),
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
        restaurant, product = self._default_restaurant_product(query_info)
        averages = await self._collect_live_rows(query_info, restaurant, product)
        if not averages:
            return self._no_live_data_response("prices", query_info, product, restaurant)

        etas = [row.get("avg_eta_min", 0) for row in averages if row.get("avg_eta_min") is not None]
        delivery_fees = [
            row.get("avg_delivery_fee", 0)
            for row in averages
            if row.get("avg_delivery_fee") is not None
        ]

        return {
            "action": "prices",
            "source_type": "live_agent",
            "fallback_used": False,
            "zone_type": "all",
            "restaurant": restaurant,
            "product": product,
            "avg_delivery_fee": round(sum(delivery_fees) / len(delivery_fees), 2)
            if delivery_fees
            else None,
            "avg_eta_min": round(sum(etas) / len(etas)) if etas else 0,
            "total_records": len(averages),
            "platform_averages": averages,
            "sources": self._sources_from_rows(averages),
            "source_urls": self._sources_from_rows(averages),
            "top_promos": [],
            "averages": averages,
            "plotly": self._plotly_platform_bars(
                "Delivery fee promedio",
                averages,
                "avg_delivery_fee",
                "MXN",
            ),
            "message": self._explain_platform_rows(
                f"Precios live por plataforma para {product}",
                averages,
                "avg_total_cost",
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _action_etas(self, query_info) -> dict:
        restaurant, product = self._default_restaurant_product(query_info)
        rows = await self._collect_live_rows(query_info, restaurant, product)
        etas = [
            {
                "platform": row.get("platform"),
                "restaurant": restaurant,
                "product": product,
                "avg_min": row.get("avg_eta_min"),
                "avg_eta_min": row.get("avg_eta_min"),
                "source_url": row.get("source_url"),
                "confidence": row.get("confidence"),
            }
            for row in rows
            if row.get("avg_eta_min") is not None
        ]
        if not etas:
            return self._no_live_data_response("etas", query_info, product, restaurant)

        return {
            "action": "etas",
            "source_type": "live_agent",
            "fallback_used": False,
            "restaurant": restaurant,
            "product": product,
            "zone": "all",
            "ETAs": etas,
            "etas": etas,
            "sources": self._sources_from_rows(rows),
            "source_urls": self._sources_from_rows(rows),
            "plotly": self._plotly_eta(etas),
            "message": self._explain_platform_rows(
                f"Tiempos live de entrega para {restaurant}",
                rows,
                "avg_eta_min",
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def _action_trends(self, query_info) -> dict:
        restaurant, product = self._default_restaurant_product(query_info)
        snapshot = await self._collect_live_rows(query_info, restaurant, product)
        if not snapshot:
            return self._no_live_data_response("trends", query_info, product, restaurant)

        return {
            "action": "trends",
            "source_type": "live_agent",
            "fallback_used": False,
            "product": product,
            "restaurant": restaurant,
            "zone": query_info.get("zone") or "all",
            "days": query_info.get("days", 7),
            "note": (
                "Snapshot live generado por el agente. Para tendencia historica real se "
                "requieren ejecuciones programadas."
            ),
            "snapshot": snapshot,
            "sources": self._sources_from_rows(snapshot),
            "source_urls": self._sources_from_rows(snapshot),
            "plotly": self._plotly_platform_bars(
                "Snapshot live de costo total",
                snapshot,
                "avg_total_cost",
                "Costo total MXN",
            ),
            "message": self._explain_platform_rows(
                f"Snapshot live competitivo para {product}",
                snapshot,
                "avg_total_cost",
            ),
            "timestamp": datetime.utcnow().isoformat(),
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

        zone = None
        if "high" in message_lower or "alta" in message_lower:
            zone = "high"
        elif "mid" in message_lower or "media" in message_lower:
            zone = "mid"
        elif "periphery" in message_lower or "perifer" in message_lower:
            zone = "periphery"

        days = 7
        for candidate in (7, 14, 30):
            if str(candidate) in message_lower:
                days = candidate

        metric = "price"
        if "eta" in message_lower or "tiempo" in message_lower:
            metric = "eta"
        elif "delivery_fee" in message_lower or "delivery fee" in message_lower:
            metric = "delivery_fee"
        elif "service_fee" in message_lower or "service fee" in message_lower:
            metric = "service_fee"

        action = None
        for action_key in self._predefined_actions:
            if action_key in message_lower:
                action = action_key
                break

        return {
            "action": action,
            "restaurant": restaurant,
            "product": product,
            "platforms": platforms,
            "location": location,
            "zone": zone,
            "days": days,
            "metric": metric,
            "raw_message": message,
            "is_predefined": action is not None,
        }

    def _period(self, records):
        if not records:
            return {"start": "", "end": ""}
        return {
            "start": min(record.scraped_at for record in records),
            "end": max(record.scraped_at for record in records),
        }

    def _plotly_platform_bars(self, title, rows, value_key, y_title):
        return {
            "data": [
                {
                    "type": "bar",
                    "x": [row.get("platform", "") for row in rows],
                    "y": [row.get(value_key, 0) for row in rows],
                    "name": y_title,
                }
            ],
            "layout": {
                "title": title,
                "xaxis": {"title": "Plataforma"},
                "yaxis": {"title": y_title},
                "template": "plotly_white",
            },
        }

    def _plotly_rankings(self, rows, value_key):
        return {
            "data": [
                {
                    "type": "bar",
                    "x": [f"{row.get('platform', '')} {row.get('zone_type', '')}" for row in rows],
                    "y": [row.get(value_key, row.get("metric_value", 0)) for row in rows],
                    "name": "Ranking",
                }
            ],
            "layout": {
                "title": "Ranking competitivo",
                "xaxis": {"title": "Plataforma / Zona"},
                "yaxis": {"title": "Valor"},
                "template": "plotly_white",
            },
        }

    def _plotly_eta(self, rows):
        return {
            "data": [
                {
                    "type": "bar",
                    "x": [row.get("platform", "") for row in rows],
                    "y": [row.get("avg_min", 0) for row in rows],
                    "name": "ETA promedio",
                }
            ],
            "layout": {
                "title": "Tiempo de entrega por plataforma",
                "xaxis": {"title": "Plataforma"},
                "yaxis": {"title": "Minutos"},
                "template": "plotly_white",
            },
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
