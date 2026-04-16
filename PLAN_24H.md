# Plan de 24 Horas - Sistema de Análisis Inteligente Rappi

## 1. Resumen Ejecutivo

Construir un sistema completo de scraping y análisis multi-plataforma (Uber Eats, Rappi, Didi Food) para comparar precios, tiempos de entrega y promociones en diferentes zonas de CDMX.

---

## 2. Estructura del Proyecto

```
prueba_tec/
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── ADR/
│   │   └── arquitectura.md
│   └── api/
│       └── openapi.yaml
├── src/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── analytics.py
│   │   │   ├── comparison.py
│   │   │   └── health.py
│   │   └── models/
│   │       ├── request.py
│   │       └── response.py
│   ├── db/
│   │   ├── connection.py
│   │   ├── migrations/
│   │   │   └── 001_initial.sql
│   │   └── repositories/
│   │       ├── pricing_repository.py
│   │       └── analytics_repository.py
│   ├── etl/
│   │   ├── extractors/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   │   ├── ubereats.py
│   │   │   │   ├── rappi.py
│   │   │   └── didi.py
│   │   ├── transformers/
│   │   │   ├── __init__.py
│   │   │   ├── normalize.py
│   │   │   └── enrich.py
│   │   └── loaders/
│   │       ├── __init__.py
│   │       └── warehouse.py
│   ├── scheduler/
│   │   └── jobs.py
│   └── shared/
│       ├── config.py
│       ├── constants.py
│       ├── exceptions.py
│       ├── logging.py
│       └── utils.py
├── tests/
│   ├── conftest.py
│   ├── integration/
│   │   └── test_api.py
│   └── unit/
│       ├── test_extractors.py
│       └── test_transformers.py
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── uv.lock
├── .env.example
└── README.md
```

---

## 3. Modelo Entidad-Relación (Base de Datos)

### 3.1 Tablas Principales

```sql
-- Plataforma: Uber Eats, Rappi, Didi Food
CREATE TABLE platforms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    base_url VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Zonas geográficas de CDMX
CREATE TABLE zones (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    zone_type VARCHAR(20) NOT NULL CHECK (zone_type IN ('high', 'mid', 'periphery')),
    coordinates GEOMETRY(Point, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Direcciones guardadas por zona
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    zone_id INTEGER REFERENCES zones(id),
    full_address VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Restaurantes objetivo
CREATE TABLE restaurants (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(id),
    external_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    rating DECIMAL(2,1),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform_id, external_id)
);

-- Productos de referencia
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(id),
    external_id VARCHAR(100),
    restaurant_id INTEGER REFERENCES restaurants(id),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform_id, external_id)
);

-- Datos scrapeados (raw)
CREATE TABLE raw_scrape (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(id),
    address_id INTEGER REFERENCES addresses(id),
    restaurant_id INTEGER REFERENCES restaurants(id),
    product_id INTEGER REFERENCES products(id),
    product_price DECIMAL(10,2),
    delivery_fee DECIMAL(10,2),
    service_fee DECIMAL(10,2),
    estimated_time_min INTEGER,
    active_promo TEXT,
    scraped_at TIMESTAMP DEFAULT NOW(),
    raw_json JSONB,
    error TEXT
);

-- Datos procesados para análisis
CREATE TABLE price_analytics (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(id),
    address_id INTEGER REFERENCES addresses(id),
    restaurant_id INTEGER REFERENCES restaurants(id),
    product_id INTEGER REFERENCES products(id),
    product_price DECIMAL(10,2),
    delivery_fee DECIMAL(10,2),
    total_cost DECIMAL(10,2) GENERATED ALWAYS AS (product_price + delivery_fee) STORED,
    estimated_time_min INTEGER,
    promo_applied VARCHAR(100),
    scraped_at DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(platform_id, address_id, product_id, scraped_at)
);

-- Promociones activas
CREATE TABLE promotions (
    id SERIAL PRIMARY KEY,
    platform_id INTEGER REFERENCES platforms(id),
    restaurant_id INTEGER REFERENCES restaurants(id),
    promo_code VARCHAR(50),
    description TEXT,
    discount_percent DECIMAL(5,2),
    min_order_amount DECIMAL(10,2),
    valid_from DATE,
    valid_until DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.2 Índices Optimizados

```sql
CREATE INDEX idx_raw_scrape_platform_address ON raw_scrape(platform_id, address_id, scraped_at);
CREATE INDEX idx_raw_scrape_product ON raw_scrape(product_id, scraped_at);
CREATE INDEX idx_price_analytics_date ON price_analytics(scraped_at);
CREATE INDEX idx_price_analytics_zone ON price_analytics(address_id, scraped_at);
CREATE INDEX idx_zones_type ON zones(zone_type);
```

---

## 4. Plan de Ejecución (24 Horas)

###Bloque 1: Fundamentos (Horas 0-6)

| Hora | Tarea | Entregable |
|------|-------|------------|
| 0-1 | Setup proyecto + docker | pyproject.toml, Dockerfile, docker-compose.yml |
| 1-2 | Config db/postgres + schemata | migrations/001_initial.sql, connection.py |
| 2-3 | Modelos Pydantic | models/request.py, models/response.py |
| 3-4 | API básica + health check | main.py con /health |
| 4-6 | Test integración smoke | tests/integration/test_api.py |

**Objetivo**: API corriendo con DB conectada

###Bloque 2: Scrapers (Horas 6-12)

| Hora | Tarea | Entregable |
|------|-------|------------|
| 6-7 | Refactor ubereats_scraper → base + ubereats | extractors/base.py, extractors/ubereats.py |
| 7-8 | Implementar rappi scraper | extractors/rappi.py |
| 8-9 | Implementar didi scraper | extractors/didi.py |
| 9-10 | ETL loader + warehouse | loaders/warehouse.py |
| 10-12 | Pipeline end-to-end test | data/ubereats_raw.json |

**Objetivo**: Los 3 scrapers funcionales

###Bloque 3: Analytics API (Horas 12-18)

| Hora | Tarea | Entregable |
|------|-------|------------|
| 12-13 | Repository layer | repositories/pricing_repository.py |
| 13-14 | Endpoint: /analytics/compare | routes/comparison.py |
| 14-15 | Endpoint: /analytics/prices | routes/analytics.py |
| 16-17 | Endpoint: /analytics/ETAs | routes/analytics.py |
| 17-18 | Scheduler jobs | scheduler/jobs.py |

**Objetivo**: API completa con endpoints

###Bloque 4: Testing y Docs (Horas 18-24)

| Hora | Tarea | Entregable |
|------|-------|------------|
| 18-19 | Unit tests scrapers | tests/unit/test_extractors.py |
| 19-20 | Unit tests transformers | tests/unit/test_transformers.py |
| 20-21 | API load tests | tests/integration/test_api.py |
| 21-22 | README + deploy notes | README.md |
| 22-24 | Buffer + QA final | - |

**Objetivo**: Sistema documentado y funcional

---

## 5. Diseño de API (Endpoints)

### 5.1 Health
```bash
GET /api/v1/health
```
Response: `{"status": "healthy", "timestamp": "2026-04-16T..."}`

### 5.2 Comparación de Precios
```bash
GET /api/v1/analytics/compare?product=Big%20Mac&zone=high
```
Response:
```json
{
  "product": "Big Mac",
  "zone": "high",
  "results": [
    {"platform": "ubereats", "price": 149.0, "delivery_fee": 29.0, "total": 178.0},
    {"platform": "rappi", "price": 145.0, "delivery_fee": 35.0, "total": 180.0},
    {"platform": "didi", "price": 159.0, "delivery_fee": 25.0, "total": 184.0}
  ],
  "best_option": "ubereats",
  "savings_vs_avg": 3.0
}
```

### 5.3 Análisis por Zona
```bash
GET /api/v1/analytics/prices?zone_type=high&start_date=2026-04-01&end_date=2026-04-15
```
Response:
```json
{
  "zone_type": "high",
  "period": {"start": "2026-04-01", "end": "2026-04-15"},
  "avg_delivery_fee": 32.5,
  "avg_eta_min": 28,
  "total_records": 156,
  "top_promos": [...]
}
```

### 5.4 Tiempos de Entrega
```bash
GET /api/v1/analytics/ETAs?restaurant=McDonald's&zone=mid
```
Response:
```json
{
  "restaurant": "McDonald's",
  "zone": "mid",
  "ETAs": [
    {"platform": "ubereats", "avg_min": 25, "min": 20, "max": 35},
    {"platform": "rappi", "avg_min": 30, "min": 22, "max": 45},
    {"platform": "didi", "avg_min": 28, "min": 18, "max": 40}
  ]
}
```

### 5.5 Rankings
```bash
GET /api/v1/analytics/rankings?metric=price&zone_type=periphery&limit=10
```

---

## 6. Pipeline ETL

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   EXTRACT   │────▶│  TRANSFORM │────▶│    LOAD   │────▶│  ANALYZE  │
│            │     │            │     │            │     │            │
│ - ubereats │     │ - normalize│     │ - raw_scrape│    │ - reports │
│ - rappi    │     │ - validate │     │ - warehouse│    │ - alerts  │
│ - didi     │     │ - enrich   │     │ - analytics│    │ - APIs   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### 6.1 Transformaciones
1. **Normalize**: Estandarizar nombres de productos, limpar precios
2. **Validate**: Verificar rangos válidos, detectar outliers
3. **Enrich**: Agregar zone_type, calcular total_cost

---

## 7. Comandos para Ejecutar

```bash
# Desarrollo
docker-compose up -d
uv sync
uv run python -m src.api.main

# Scraping manual
uv run python -m src.etl.extractors.ubereats
uv run python -m src.etl.extractors.rappi
uv run python -m src.etl.extractors.didi

# Tests
uv run pytest tests/ -v
uv run pytest tests/ --cov=src

# Production
docker build -t rappi-analyzer .
docker run -p 8000:8000 rappi-analyzer
```

---

## 8.Cómo Abordar el Problema

### Estrategia Principal

1. **Paralelización**: Los 3 scrapers pueden correr en paralelo (procesos separados)
2. **Rate Limiting**: Respetar límites de cada plataforma
3. **Fallbacks**: Retry con backoff exponencial
4. **Checkpointing**: Guardar estado cada dirección procesada
5. **Monitoreo**: Logs estructurados + métricas

### Manejo de Errores

- **Timeout**: Retry 3x, luego marcar como failed
- **Captcha**: Backoff largo + notificar
- **Bloqueo IP**: Rotar proxy si disponible
- **Data quality**: Validación post-scrape

### Siguientes Pasos (Post-24h)

1. Dashboard UI (streamlit/gradio)
2. ML forecasting de precios
3. Alertas de promociones
4. API de predicciones
5. Proxy rotation