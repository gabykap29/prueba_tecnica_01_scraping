# Rappi Competitive Intelligence

Sistema de competitive intelligence para comparar Rappi contra Uber Eats y DiDi Food en Mexico usando scraping, datos de respaldo reproducibles, API analitica y reporte ejecutivo.

## Scope

- Plataformas: Rappi, Uber Eats y DiDi Food.
- Geografia: 20 direcciones representativas de CDMX.
- Zonas: high, mid y periphery.
- Productos comparables: Big Mac, Combo Big Mac, Whopper y Combo Whopper.
- Metricas: precio de producto, delivery fee, service fee, ETA, promocion visible, disponibilidad y costo total calculado.

El scraping real puede fallar por bloqueos, cambios de HTML o disponibilidad. Por eso el repositorio incluye `sample_data/competitive_snapshot.csv` como plan B para demo y evaluacion reproducible.

## Setup

```bash
python -m venv env
.\env\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Con `uv`:

```bash
uv sync
uv run playwright install chromium
```

## Ejecutar API

```bash
.\env\Scripts\python.exe run_api.py
```

Endpoints principales:

- `GET /api/v1/health`
- `GET /api/v1/analytics/summary`
- `GET /api/v1/analytics/compare?product=Big%20Mac&zone=high`
- `GET /api/v1/analytics/prices?zone_type=periphery`
- `GET /api/v1/analytics/ETAs?restaurant=McDonald's`
- `GET /api/v1/analytics/rankings?metric=price&zone_type=mid`

## Generar Datos De Respaldo

```bash
.\env\Scripts\python.exe scripts\generate_sample_data.py
```

Output:

- `sample_data/competitive_snapshot.csv`

Este archivo contiene 240 observaciones: 20 direcciones x 3 plataformas x 4 productos.

## Ejecutar Scrapers

Cada scraper se puede ejecutar de forma independiente:

```bash
.\env\Scripts\python.exe -m src.etl.extractors.rappi
.\env\Scripts\python.exe -m src.etl.extractors.ubereats
.\env\Scripts\python.exe -m src.etl.extractors.didi
```

O ejecutar las tres plataformas con un solo comando:

```bash
.\env\Scripts\python.exe scripts\run_scrapers.py
```

Los scrapers usan Playwright, user agents rotativos, delays y deteccion basica de bloqueo. En demo, usar `sample_data/competitive_snapshot.csv` como backup si los sitios bloquean o cambian selectores.

### Primer Scraper Live Validado: Rappi

Para correr un scrape live acotado de Rappi:

```bash
.\env\Scripts\python.exe scripts\scrape_rappi_live.py --limit-addresses 1 --limit-restaurants 1 --output data\live_rappi_snapshot.csv
```

Luego mezcla los registros live con el backup para alimentar la API:

```bash
.\env\Scripts\python.exe scripts\build_live_snapshot.py
```

Output activo:

- `data/live_rappi_snapshot.csv`: evidencia cruda del scrape de Rappi.
- `data/competitive_snapshot.csv`: snapshot usado por la API cuando existe.

La API prioriza `data/competitive_snapshot.csv`; si no existe, usa `sample_data/competitive_snapshot.csv`.

### Scrapers Live De Uber Eats Y DiDi

Tambien hay runners live acotados para Uber Eats y DiDi:

```bash
.\env\Scripts\python.exe scripts\scrape_ubereats_live.py --limit-addresses 1 --limit-restaurants 1 --output data\live_ubereats_snapshot.csv
.\env\Scripts\python.exe scripts\scrape_didi_live.py --limit-addresses 1 --limit-restaurants 1 --output data\live_didi_snapshot.csv
```

En la corrida local inicial:

- Uber Eats navego la URL con `pl` + `q`, pero devolvio bloqueo/captcha.
- DiDi Food cargo `https://web.didiglobal.com/mx/food/`, pero no expuso el restaurante en la pagina renderizada sin interaccion adicional.

Estos resultados quedan en los CSV live como evidencia y la API los expone en `live_scrape_status`.

## Generar Informe Ejecutivo

```bash
.\env\Scripts\python.exe scripts\generate_report.py
```

Output:

- `reports/competitive_intelligence_report.html`

El reporte incluye:

- Top 5 insights accionables con finding, impacto y recomendacion.
- Grafico de costo total promedio por plataforma.
- Grafico de ETA promedio por plataforma.
- Grafico de delivery fee promedio por plataforma.
- Grafico de promociones visibles.
- Tabla de variabilidad geografica por zona.

## Tests

```bash
.\env\Scripts\python.exe -m pytest
```

La suite cubre carga del dataset, comparaciones, resumen ejecutivo, rutas de API y generacion del reporte.

## Docker

```bash
docker-compose up --build
```

La API queda disponible en `http://localhost:8000`.

## Consideraciones Eticas Y Limitaciones

- Usar rate limiting y delays razonables.
- No sobrecargar servidores de terceros.
- Respetar `robots.txt` cuando sea aplicable.
- Documentar bloqueos, captchas y datos no disponibles.
- Los selectores HTML de plataformas pueden cambiar sin aviso.
- El dataset incluido es deterministico y sirve como plan B de demo, no como medicion real de mercado.

## Presentacion Sugerida

1. Explicar scope: fast food, 20 direcciones, 3 plataformas.
2. Mostrar ejecucion de API o reporte.
3. Mostrar `sample_data/competitive_snapshot.csv` como backup reproducible.
4. Presentar el top 5 de insights desde `reports/competitive_intelligence_report.html`.
5. Cerrar con limitaciones: robustez de scraping, necesidad de proxies y scrapes programados para tendencia temporal.
