# Rappi Competitive Intelligence

Sistema de competitive intelligence para comparar Rappi contra Uber Eats y DiDi Food en Mexico usando scraping, datos de respaldo reproducibles, API analitica y reporte ejecutivo.

**Repositorio Backend**: https://github.com/gabykap29/prueba_tecnica_01_scraping.git
**Repositorio Frontend**: https://github.com/gabykap29/prueba_tecnica_scraping_01_client.git

## Demo

### Video de demostración

Mira el video de funcionamiento del sistema:

<details>
<summary>Ver video demo</summary>

https://github.com/user-attachments/files/video-demo.mp4

</details>

O descarga directamente: [video-demo.mp4](files/video-demo.mp4)

---

## Scope

- Plataformas: Rappi, Uber Eats y DiDi Food.
- Geografia: 20 direcciones representativas de CDMX.
- Zonas: high, mid y periphery.
- Productos comparables: Big Mac, Combo Big Mac, Whopper y Combo Whopper.
- Metricas: precio de producto, delivery fee, service fee, ETA, promocion visible, disponibilidad y costo total calculado.

El scraping real puede fallar por bloqueos, cambios de HTML o disponibilidad. Por eso el repositorio incluye `sample_data/competitive_snapshot.csv` como plan B para demo y evaluacion reproducible.

## Instalación

### 1. Clonar el repositorio

```bash
git clone <repo-url>
cd prueba_tec
```

### 2. Crear y activar entorno virtual

```bash
# Con Python
python -m venv env
.\env\Scripts\activate

# O con uv
uv sync
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt

# Instalar Playwright
playwright install chromium

# Instalar dependencias del proyecto
pip install -e .
```

### 4. Configurar variables de entorno

Crear archivo `.env` en la raíz:

```env
# Base de datos (opcional)
DATABASE_URL=postgresql://user:pass@localhost:5432/rappi_analytics

# APIs Externas (opcional para OSINT)
SERPAPI_API_KEY=your_serpapi_key
GEMINI_API_KEY=your_gemini_key

# Frontend
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

### Cómo obtener las API Keys

#### SerpAPI (para búsqueda OSINT)

SerpAPI se usa para buscar precios en Google cuando el scraping falla.

1. **Regístrate** en: https://serpapi.com
2. Usa tu cuenta **GitHub** o **Google**
3. Verifica tu **email** y **teléfono**
4. Elije el plan **Free** (100 búsquedas/mes gratis) o uno de pago
5. Ve a **Manage API Key** en el dashboard
6. Copia tu API key

Gratis: 250 búsquedas/mes (U.S. Legal Shield, ZeroTrace Mode)
Paid: Desde $75/mes para más búsquedas

#### Google Gemini API (para el agente conversacional)

Gemini se usa para el agente de IA conversacional.

1. **Regístrate** en: https://aistudio.google.com/app/apikey
2. Haz clic en **Create API Key**
3. Copia la key

Gratis (con límites): 15 requests/min, 1M tokens/day
 paid: $0.35-$0.50 / 1M tokens

### 5. Instalar frontend

```bash
cd rappi-analytics-web
npm install

# Copiar logo de Rappi
cp rappi-seeklogo.png public/rappi-logo.png
```

## Ejecución

### 1. Iniciar Backend ( FastAPI)

```bash
python run_api.py
```

La API estará disponible en: `http://127.0.0.1:8000`

Documentación Swagger: `http://127.0.0.1:8000/docs`

### 2. Iniciar Frontend (Next.js)

```bash
cd rappi-analytics-web
npm run dev
```

La aplicación estará disponible en: `http://localhost:3000`

### 3. Verificar que todo funciona

```bash
# Health check
curl http://127.0.0.1:8000/api/v1/health

# Comparar precios
curl "http://127.0.0.1:8000/api/v1/analytics/compare?product=Big%20Mac"

# Chat con agente IA
curl -X POST http://127.0.0.1:8000/api/v1/ai-agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "ayuda"}'
```

---

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

Los scrapers usan Playwright, `playwright-stealth`, un User-Agent moderno y consistente, delays y deteccion basica de bloqueo. En demo, usar `sample_data/competitive_snapshot.csv` como backup si los sitios bloquean o cambian selectores.

Variables utiles para scraping live:

```bash
set SCRAPER_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/143.0.0.0 Safari/537.36
set SCRAPER_CAPTCHA_PROVIDER=2captcha
set SCRAPER_CAPTCHA_API_KEY=tu_api_key
```

El solver de captcha es opcional. Los proveedores soportados son `2captcha`, `capsolver`, `anti-captcha` y `anticaptcha`. Si el scraper detecta un reCAPTCHA/hCaptcha y no hay proveedor configurado, escribe `captcha_solver_not_configured` en el CSV live y mantiene el fallback CSV.

### Primer Scraper Live Validado: Rappi

Para correr un scrape live acotado de Rappi:

```bash
.\env\Scripts\python.exe scripts\scrape_rappi_live.py --limit-addresses 1 --limit-restaurants 1 --output data\live_rappi_snapshot.csv
```

Si ya existe una sesion validada de Playwright, se puede reutilizar:

```bash
.\env\Scripts\python.exe scripts\scrape_rappi_live.py --storage-state data\storage_state.json --limit-addresses 1 --limit-restaurants 1
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

Tambien soportan `--storage-state data\storage_state.json` para reutilizar cookies, ubicacion y preferencias capturadas en una navegacion manual previa.

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
