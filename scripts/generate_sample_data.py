"""Generate deterministic backup data for the competitive intelligence demo."""

from __future__ import annotations

import csv
from pathlib import Path


ADDRESSES = [
    ("Presidente Masaryk 61, Polanco, CDMX", "high"),
    ("Moliere 222, Polanco, CDMX", "high"),
    ("Av. Santa Fe 495, Cuajimalpa, CDMX", "high"),
    ("Emilio Castelar 95, Polanco, CDMX", "high"),
    ("Av. Insurgentes Sur 664, Del Valle, CDMX", "high"),
    ("Av. Alvaro Obregon 110, Roma Norte, CDMX", "mid"),
    ("Tamaulipas 66, Condesa, CDMX", "mid"),
    ("Medellin 65, Roma Sur, CDMX", "mid"),
    ("Av. Coyoacan 1035, Del Valle, CDMX", "mid"),
    ("Gabriel Mancera 1402, Del Valle, CDMX", "mid"),
    ("Av. Revolucion 1400, San Angel, CDMX", "mid"),
    ("Eje Central 18, Centro Historico, CDMX", "mid"),
    ("Av. Hidalgo 45, Centro, CDMX", "mid"),
    ("Av. Tlahuac 3000, Iztapalapa, CDMX", "periphery"),
    ("Av. Ermita Iztapalapa 1020, Iztapalapa, CDMX", "periphery"),
    ("Av. Zaragoza 600, Iztapalapa, CDMX", "periphery"),
    ("Av. Canal de Garay 50, Xochimilco, CDMX", "periphery"),
    ("Calzada de Tlalpan 2800, Xochimilco, CDMX", "periphery"),
    ("Av. Texcoco 45, Venustiano Carranza, CDMX", "periphery"),
    ("Av. Vallejo 880, Gustavo A. Madero, CDMX", "periphery"),
]

PRODUCTS = [
    ("McDonald's", "Big Mac", 99),
    ("McDonald's", "Combo Big Mac", 149),
    ("Burger King", "Whopper", 109),
    ("Burger King", "Combo Whopper", 159),
]

PLATFORM_RULES = {
    "rappi": {
        "product": 1.00,
        "delivery": 35,
        "service": 10,
        "eta": 31,
        "promo": "15% off",
        "source_url": "https://www.rappi.com.mx",
        "search_url": "https://www.rappi.com.mx/buscar?q={query}",
    },
    "ubereats": {
        "product": 1.02,
        "delivery": 29,
        "service": 9,
        "eta": 28,
        "promo": "20% off",
        "source_url": "https://www.ubereats.com/mx",
        "search_url": "https://www.ubereats.com/mx/search?q={query}",
    },
    "didi": {
        "product": 0.98,
        "delivery": 32,
        "service": 7,
        "eta": 30,
        "promo": "free delivery",
        "source_url": "https://www.didifood.com/mx",
        "search_url": "https://www.didifood.com/mx/search?q={query}",
    },
}

ZONE_ADJUSTMENTS = {
    "high": {"delivery": -4, "eta": -3, "product": 1.04},
    "mid": {"delivery": 0, "eta": 0, "product": 1.00},
    "periphery": {"delivery": 8, "eta": 6, "product": 0.96},
}


def main() -> None:
    output_path = Path("sample_data/competitive_snapshot.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "platform",
        "address",
        "zone_type",
        "restaurant",
        "product_name",
        "product_price",
        "delivery_fee",
        "service_fee",
        "estimated_time_min",
        "active_promo",
        "availability",
        "scraped_at",
        "source_url",
        "search_url",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for address_index, (address, zone_type) in enumerate(ADDRESSES):
            zone = ZONE_ADJUSTMENTS[zone_type]
            for platform, rules in PLATFORM_RULES.items():
                for product_index, (restaurant, product_name, base_price) in enumerate(PRODUCTS):
                    local_noise = ((address_index + product_index) % 4) - 1
                    product_price = round(base_price * rules["product"] * zone["product"] + local_noise, 2)
                    delivery_fee = rules["delivery"] + zone["delivery"] + (address_index % 3)
                    if platform == "rappi" and zone_type == "periphery":
                        delivery_fee += 4
                    service_fee = rules["service"] + (product_index % 2)
                    eta = rules["eta"] + zone["eta"] + (address_index % 5)
                    promo = rules["promo"] if (address_index + product_index) % 3 != 0 else ""
                    availability = "closed" if platform == "didi" and address_index in (17, 19) else "available"
                    writer.writerow(
                        {
                            "platform": platform,
                            "address": address,
                            "zone_type": zone_type,
                            "restaurant": restaurant,
                            "product_name": product_name,
                            "product_price": product_price,
                            "delivery_fee": delivery_fee,
                            "service_fee": service_fee,
                            "estimated_time_min": eta,
                            "active_promo": promo,
                            "availability": availability,
                            "scraped_at": "2026-04-17T20:00:00Z",
                            "source_url": rules["source_url"],
                            "search_url": rules["search_url"].format(
                                query=restaurant.replace(" ", "+")
                            ),
                        }
                    )

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
