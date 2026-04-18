# AI Agent para Rappi Analytics

Agente inteligente basado en Pydantic AI para extracción de datos de delivery, alternativa robusta a los scrapers tradicionales que usan Playwright.

## Características

- **Conversaciones en tiempo real**: Chat con streaming de estados
- **Estados visibles**: understanding ? searching ? extracting ? validating ? comparing ? completed
- **Extracción sin scraping**: Usa SerpAPI + Google Gemini para obtener precios actuales
- **Datos estructurados**: Salida tipada con Pydantic
- **Múltiples plataformas**: Soporta Rappi, Uber Eats y Didi Food

## Estados del Agente

Durante el procesamiento, el agente emite estados en tiempo real:

| Estado | Descripción | Progreso |
|--------|-------------|----------|
| `understanding` | Analizando tu consulta... | 10% |
| `searching` | Buscando en [plataforma]... | 30-45% |
| `extracting` | Procesando resultados... | 60% |
| `validating` | Validando información... | 75% |
| `comparing` | Comparando opciones... | 85% |
| `completed` | ¡Listo! | 100% |
| `error` | Error en el procesamiento | - |

## Configuración

1. Copiar `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```

2. Configurar las API keys:
   - `GEMINI_API_KEY`: Tu API key de Google AI Studio
   - `SERPAPI_API_KEY`: Tu API key de SerpAPI

## Endpoints API

### Chat con Streaming (SSE)
```
GET /api/v1/ai-agent/chat/stream?message=Cuanto cuesta un Big Mac&conversation_id=123
```

Respuesta SSE:
```json
event: message
data: {"status": "understanding", "message": "Analizando tu consulta...", "progress": 10}

data: {"status": "searching", "message": "Buscando en rappi...", "progress": 30}

data: {"status": "searching", "message": "Buscando en ubereats...", "progress": 45}

data: {"status": "extracting", "message": "Procesando los resultados encontrados...", "progress": 60}

data: {"status": "validating", "message": "Validando la informacion...", "progress": 75}

data: {"status": "comparing", "message": "Comparando opciones entre plataformas...", "progress": 85}

data: {"status": "completed", "message": "Listo!", "progress": 100, "response_text": "Encontré...", "data": {...}}
```

### Chat Simple (POST)
```
POST /api/v1/ai-agent/chat
{
  "message": "Cuanto cuesta un Big Mac?",
  "conversation_id": "user-123"
}
```

### Historial de Conversación
```
GET /api/v1/ai-agent/conversations/{conversation_id}
```

### Limpiar Conversación
```
DELETE /api/v1/ai-agent/conversations/{conversation_id}
```

### Endpoints Legados
- `GET /api/v1/ai-agent/search` - Buscar precio de un producto
- `GET /api/v1/ai-agent/compare` - Comparar en todas las plataformas
- `GET /api/v1/ai-agent/health` - Verificar estado del agente
- `GET /api/v1/ai-agent/quick-compare/{product}` - Comparación rápida

## Ejemplo de uso con JavaScript

```javascript
// Usando Server-Sent Events
const message = "Cuanto cuesta un Big Mac en McDonald's?";
const eventSource = new EventSource(
  `/api/v1/ai-agent/chat/stream?message=${encodeURIComponent(message)}`
);

eventSource.onmessage = (event) => {
  const state = JSON.parse(event.data);
  
  // Actualizar UI con el estado
  updateProgress(state.progress);
  updateStatusMessage(state.message);
  
  if (state.status === 'completed') {
    showResult(state.response_text, state.data);
    eventSource.close();
  }
};

eventSource.onerror = (error) => {
  console.error('Error:', error);
  eventSource.close();
};
```

## Estructura

```
src/ai_agent/
+-- __init__.py      # Exportaciones del módulo
+-- models.py        # Modelos Pydantic (incluye AgentState, AgentMessage)
+-- agent.py         # Agente con soporte de conversación
+-- router.py        # Endpoints de FastAPI con SSE
```

## Modelo

- **Proveedor**: Google Gemini
- **Modelo**: gemini-2.0-flash
- **Ventajas**: Gratis (con límites), respuestas rápidas, buena extracción de datos

## Detección Automática

El agente detecta automáticamente:
- **Restaurantes**: McDonald's, Burger King, KFC, Wendy's
- **Productos**: Big Mac, Whopper, Nuggets, Papas
- **Plataformas**: Rappi, Uber Eats, Didi Food
- **Zonas**: Polanco, Roma/Condesa, Santa Fe
