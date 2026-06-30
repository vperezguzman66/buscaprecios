# BuscaPrecios

Aplicación web para comparar precios de productos en las principales tiendas de mejoramiento del hogar de Chile: **Easy**, **Homecenter (Sodimac)**, **Construmart**, **Imperial** y **MercadoLibre**.

## Características

- **Búsqueda simple** — escribe un producto y obtén resultados de todas las tiendas en paralelo, ordenados de menor a mayor precio
- **Búsqueda en lote (CSV)** — sube un archivo con hasta 30 productos; los resultados llegan en tiempo real con barra de progreso
- **Exportar a CSV** — descarga los resultados en formato compatible con Excel (con BOM para acentos)
- **Filtro por tienda** — selecciona en qué tiendas buscar
- **Historial de búsquedas** — las últimas 10 búsquedas se guardan en el navegador como accesos rápidos
- **Caché de resultados** — búsquedas repetidas son instantáneas (caché en memoria de 5 minutos)
- Sin Playwright ni Selenium: todo con `httpx` puro (rápido y liviano)

## Requisitos

- Python 3.11 o superior
- Conexión a internet

## Instalación y uso

```bash
git clone <url-del-repo>
cd buscaprecios
./run.sh
```

El script crea el entorno virtual, instala dependencias y levanta el servidor. Abre `http://localhost:8000` en el navegador.

Para detener el servidor: `Ctrl+C`

## MercadoLibre (configuración opcional)

MercadoLibre requiere credenciales de API gratuitas. Sin ellas, la tienda aparece deshabilitada en la interfaz pero las demás siguen funcionando con normalidad.

**Pasos para activarla:**

1. Regístrate en [developers.mercadolibre.com](https://developers.mercadolibre.com) con tu cuenta de MercadoLibre
2. Crea una nueva aplicación (el nombre y la URL pueden ser cualquier cosa)
3. Copia el **Client ID** y el **Secret Key**
4. Crea el archivo `.env` en la raíz del proyecto:

```bash
ML_CLIENT_ID=tu_client_id_aqui
ML_CLIENT_SECRET=tu_client_secret_aqui
```

5. Reinicia el servidor con `./run.sh`

El servidor mostrará `MercadoLibre: habilitado ✓` al arrancar.

## Estructura del proyecto

```
buscaprecios/
├── backend/
│   ├── main.py               # API FastAPI
│   ├── requirements.txt
│   └── scrapers/
│       ├── base.py           # Dataclass Product y clase base BaseScraper
│       ├── easy.py           # Scraper Easy.cl
│       ├── homecenter.py     # Scraper Homecenter / Sodimac
│       ├── construmart.py    # Scraper Construmart
│       ├── imperial.py       # Scraper Imperial.cl
│       └── mercadolibre.py  # Scraper MercadoLibre (requiere credenciales)
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── .env.example              # Plantilla de variables de entorno
└── run.sh
```

## API

El backend expone una API REST en `http://localhost:8000`.

### `GET /api/search`

Busca un producto en una o más tiendas.

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `query` | string | — | Término de búsqueda (1–200 caracteres, obligatorio) |
| `stores` | string | `easy,homecenter,construmart` | Tiendas separadas por coma |
| `max_results` | int | `10` | Resultados por tienda (máximo: 20) |

**Ejemplo:**
```
GET /api/search?query=taladro+percutor&stores=easy,homecenter&max_results=5
```

**Respuesta:**
```json
{
  "query": "taladro percutor",
  "count": 10,
  "results": [
    {
      "name": "Taladro Percutor Eléctrico 13 mm 650 W",
      "price": 43989.0,
      "price_text": "$43.989",
      "url": "https://www.sodimac.cl/...",
      "image": "https://media.sodimac.cl/...",
      "store": "Homecenter (Sodimac)",
      "store_id": "homecenter",
      "sku": "110477583"
    }
  ],
  "errors": []
}
```

Los resultados vienen ordenados por precio ascendente. Los productos sin precio aparecen al final. Las tiendas que fallan incluyen una entrada en `errors` sin interrumpir los demás resultados.

**Rate limit:** 20 requests/minuto por IP.

### `POST /api/search-batch`

Busca múltiples productos desde un archivo CSV. Responde como un stream **Server-Sent Events (SSE)**: cada producto completado se envía de inmediato sin esperar a los demás.

**Body (multipart/form-data):**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `file` | archivo | CSV con un producto por línea (máx. 100 KB) |
| `stores` | string | Tiendas separadas por coma |
| `max_results` | int | Resultados por tienda por producto (1–20, default: 5) |

**Formato del CSV:**
```
pintura látex blanco
taladro percutor 13mm
cemento gris 25kg
pala punta redonda
```

**Límites:** máximo 30 productos por lote, 3 búsquedas simultáneas.

**Formato de cada evento SSE:**
```
data: {"progress": 2, "total": 4, "query": "cemento gris 25kg", "result": {...}}

data: {"done": true}
```

**Rate limit:** 5 requests/minuto por IP.

### `GET /api/stores`

Devuelve la lista de tiendas disponibles y si están configuradas.

```json
[
  { "id": "easy", "name": "Easy", "configured": true },
  { "id": "mercadolibre", "name": "MercadoLibre", "configured": false }
]
```

## Cómo funciona cada scraper

### Easy.cl

Easy usa Next.js con renderizado en servidor (SSR). La página de búsqueda embebe todos los datos del producto en un bloque `__NEXT_DATA__` dentro del HTML inicial, por lo que basta un solo request `GET`.

- **URL:** `https://www.easy.cl/search/{query}` (query URL-encoded con guiones como separador de palabras)
- **Datos:** `props.pageProps.serverProductsResponse.productList`
- **Precio:** campo `offerPrice` (oferta) o `normalPrice` (precio regular)

### Homecenter (Sodimac)

Homecenter Chile opera bajo `sodimac.cl` (homecenter.cl redirige allí eliminando los parámetros de búsqueda). También usa Next.js SSR. El query se pasa como parámetro HTTP para que httpx maneje el encoding automáticamente.

- **URL:** `https://sodimac.cl/sodimac-cl/buscar?Ntt={query}`
- **Datos:** `props.pageProps.results`
- **Precio:** array `prices[]` — se selecciona `internetPrice` (precio web); si no existe, `cmrPrice` (con tarjeta CMR). Se ignoran precios tachados (`crossed: true`).
- **Formato de precio:** la API devuelve `"43.989"` (punto = miles en Chile), se limpia con regex antes de convertir a float.

### Construmart

Construmart usa Magento 2. Su API GraphQL pública devuelve nombres e imágenes pero **no expone precios** (siempre retorna 0). Se usa una estrategia de dos pasos:

1. **GraphQL** (`POST /graphql`) → lista de productos (nombre, SKU, URL, imagen) en un solo request
2. **Páginas individuales** → se obtienen en paralelo (máx. 5 concurrentes vía semáforo); el precio se extrae del bloque `application/ld+json` (Schema.org) que Magento genera en cada página

- **GraphQL:** `https://www.construmart.cl/graphql`
- **Precio:** `offers.price` en el JSON-LD de cada página de producto

### Imperial.cl

Imperial usa Oracle Commerce Cloud (OCC). La búsqueda pasa por el endpoint `assembler/pages/.../guidedsearch` que devuelve registros con atributos de producto (nombre, SKU, precio, imagen) en formato JSON. Cuando la búsqueda redirige a una categoría, se usa un endpoint alternativo (`get-category-products`) para obtener los IDs y luego se consulta `/ccstore/v1/products` para las rutas y nombres.

- **Búsqueda:** `GET /ccstore/v1/assembler/pages/Default/services/guidedsearch?Ntt={query}`
- **Precio:** campo `sku.activePrice` en los atributos del registro
- **Categorías:** endpoint `/ccstorex/custom/occ/get-category-products` + `/ccstore/v1/products`

### MercadoLibre

Usa la [API oficial de MercadoLibre](https://developers.mercadolibre.com/es_ar/productos-y-busquedas). El scraping directo está bloqueado por detección de tráfico sospechoso.

1. **Token OAuth** — se obtiene automáticamente con `client_credentials` (dura 6 horas, se renueva en background)
2. **Búsqueda** — `GET https://api.mercadolibre.com/sites/MLC/search?q={query}&condition=new`

Si las variables `ML_CLIENT_ID` / `ML_CLIENT_SECRET` no están configuradas, el scraper lanza `MercadoLibreNotConfiguredError` que el backend convierte en un aviso en la respuesta (no en un error HTTP).

## Seguridad

| Medida | Detalle |
|--------|---------|
| Rate limiting | 20 req/min en `/api/search`, 5 req/min en `/api/search-batch` (via `slowapi`) |
| `max_results` acotado | Validado en el backend (mínimo 1, máximo 20) independiente del cliente |
| Tamaño de CSV | Rechaza archivos mayores a 100 KB (HTTP 413) |
| CORS restringido | Solo acepta requests desde `localhost:8000` |
| URL encoding correcto | `urllib.parse.quote()` en Easy; `params={}` en Homecenter (httpx lo codifica) |
| Headers de seguridad | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy` |
| Links externos | `rel="noopener noreferrer"` en todos los links de productos |
| URLs saneadas | El frontend valida que las URLs sean `http:` o `https:` antes de renderizarlas |
| `.env` seguro | Cargado con `set -a; source .env; set +a` (maneja valores con espacios) |

## Dependencias

| Paquete | Versión | Uso |
|---------|---------|-----|
| `fastapi` | 0.115.5 | Framework API |
| `uvicorn` | 0.32.1 | Servidor ASGI |
| `httpx` | 0.28.1 | Cliente HTTP async |
| `python-multipart` | 0.0.20 | Subida de archivos CSV |
| `slowapi` | 0.1.9 | Rate limiting por IP |

## Agregar una tienda nueva

1. Crea `backend/scrapers/mi_tienda.py` con una clase que extienda `BaseScraper`:

```python
from .base import BaseScraper, Product

class MiTiendaScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        # Tu lógica aquí
        return [
            Product(
                name="Nombre del producto",
                price=9990.0,
                price_text="$9.990",
                url="https://...",
                image="https://...",
                store="Mi Tienda",
                store_id="mi_tienda",
                sku="12345",
            )
        ]
```

2. Agrégala a `backend/scrapers/__init__.py` y al diccionario `SCRAPERS` de `backend/main.py`.

3. Añade su badge de color en `frontend/style.css`:

```css
.badge-mi_tienda { background: #e2d9f3; color: #432874; }
```

4. Si requiere credenciales, sigue el patrón de `mercadolibre.py`: usa `os.getenv()`, expone un `is_configured` property, y lanza una excepción específica cuando no está configurada.

## Notas técnicas

- **Construmart** es el más lento (~5–10 s) porque requiere un request adicional por producto para obtener el precio. Con `max_results=10`, lanza hasta 10 requests concurrentes (limitados a 5 simultáneos).
- **Caché:** los resultados se guardan en memoria por 5 minutos. El caché es compartido entre búsqueda simple y por lote, por lo que si ya se buscó un producto individualmente, el lote lo obtiene instantáneamente.
- **Batch SSE:** el endpoint de lote usa Server-Sent Events para enviar resultados conforme van llegando. El frontend los muestra con una barra de progreso y renderiza todo al final.
- Los scrapers dependen de la estructura actual de las páginas web. Si una tienda rediseña su sitio, el scraper correspondiente puede necesitar ajustes.
