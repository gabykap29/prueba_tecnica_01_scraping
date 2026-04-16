"""Constants module for the Rappi Analytics application.

This module contains all application-wide constants including platform URLs,
target restaurants, products, and geographic data for Mexico City.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformConstants:
    """Constants related to food delivery platforms."""

    UBEREATS_BASE_URL: str = "https://www.ubereats.com/mx"
    RAPPI_BASE_URL: str = "https://www.rappi.com.mx"
    DIDIFOOD_BASE_URL: str = "https://www.didifood.com/mx"


@dataclass(frozen=True)
class ZoneConstants:
    """Geographic zones for Mexico City delivery analysis."""

    ZONES = [
        {"address": "Presidente Masaryk 61, Polanco, CDMX", "zone": "high"},
        {"address": "Moliere 222, Polanco, CDMX", "zone": "high"},
        {"address": "Av. Santa Fe 495, Cuajimalpa, CDMX", "zone": "high"},
        {"address": "Emilio Castelar 95, Polanco, CDMX", "zone": "high"},
        {"address": "Av. Insurgentes Sur 664, Del Valle, CDMX", "zone": "high"},
        {"address": "Av. Alvaro Obregon 110, Roma Norte, CDMX", "zone": "mid"},
        {"address": "Tamaulipas 66, Condesa, CDMX", "zone": "mid"},
        {"address": "Medellin 65, Roma Sur, CDMX", "zone": "mid"},
        {"address": "Av. Coyoacan 1035, Del Valle, CDMX", "zone": "mid"},
        {"address": "Gabriel Mancera 1402, Del Valle, CDMX", "zone": "mid"},
        {"address": "Av. Revolucion 1400, San Angel, CDMX", "zone": "mid"},
        {"address": "Eje Central 18, Centro Historico, CDMX", "zone": "mid"},
        {"address": "Av. Hidalgo 45, Centro, CDMX", "zone": "mid"},
        {"address": "Av. Tlahuac 3000, Iztapalapa, CDMX", "zone": "periphery"},
        {"address": "Av. Ermita Iztapalapa 1020, Iztapalapa, CDMX", "zone": "periphery"},
        {"address": "Av. Zaragoza 600, Iztapalapa, CDMX", "zone": "periphery"},
        {"address": "Av. Canal de Garay 50, Xochimilco, CDMX", "zone": "periphery"},
        {"address": "Calzada de Tlalpan 2800, Xochimilco, CDMX", "zone": "periphery"},
        {"address": "Av. Texcoco 45, Venustiano Carranza, CDMX", "zone": "periphery"},
        {"address": "Av. Vallejo 880, Gustavo A. Madero, CDMX", "zone": "periphery"},
    ]


@dataclass(frozen=True)
class RestaurantConstants:
    """Target restaurants for price comparison."""

    TARGET_RESTAURANTS: tuple = ("McDonald's", "Burger King")
    TARGET_PRODUCTS: tuple = (
        "Big Mac",
        "Whopper",
        "Combo Big Mac",
        "Combo Whopper",
    )


@dataclass(frozen=True)
class ScrapingConstants:
    """Constants related to web scraping operations."""

    PAGE_LOAD_TIMEOUT: int = 30000
    SELECTOR_TIMEOUT: int = 5000
    MIN_REQUEST_DELAY: float = 3.0
    MAX_REQUEST_DELAY: float = 6.0
    BLOCKED_SIGNALS: tuple = (
        "captcha",
        "robot",
        "access denied",
        "blocked",
        "verify you are human",
    )


@dataclass(frozen=True)
class APIConstants:
    """Constants related to API configuration."""

    API_PREFIX: str = "/api/v1"
    API_TITLE: str = "Rappi Analytics API"
    API_VERSION: str = "1.0.0"
    API_DESCRIPTION: str = "Sistema de Analisis Inteligente para Operaciones Rappi"


PLATFORMS = ["ubereats", "rappi", "didi"]
ZONE_TYPES = ["high", "mid", "periphery"]
