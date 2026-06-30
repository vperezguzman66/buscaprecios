import asyncio
import csv
import io
import json
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from scrapers import (
    ConstrumartScraper,
    EasyScraper,
    HomecenterScraper,
    ImperialScraper,
    MercadoLibreNotConfiguredError,
    MercadoLibreScraper,
)

# ── Rate limiter ──────────────────────────────────────────────────────────────

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="BuscaPrecios API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers ──────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' https: data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self';"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── CORS — localhost only ─────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ── Scrapers ──────────────────────────────────────────────────────────────────

_ml_scraper = MercadoLibreScraper()

SCRAPERS = {
    "easy": EasyScraper(),
    "homecenter": HomecenterScraper(),
    "construmart": ConstrumartScraper(),
    "imperial": ImperialScraper(),
    "mercadolibre": _ml_scraper,
}

import os as _os, sys as _sys
if getattr(_sys, "frozen", False):
    FRONTEND_DIR = Path(_sys._MEIPASS) / "frontend"
else:
    FRONTEND_DIR = Path(_os.environ.get("BUSCAPRECIOS_BASE", str(Path(__file__).parent.parent))) / "frontend"

MAX_RESULTS = 20
MAX_CSV_BYTES = 100 * 1024  # 100 KB

# ── In-memory result cache (TTL = 5 min) ─────────────────────────────────────

_cache: dict[tuple, tuple[float, dict]] = {}
_CACHE_TTL = 300

def _cache_get(key: tuple) -> dict | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data

def _cache_set(key: tuple, data: dict) -> None:
    # Evict oldest 50 entries when approaching capacity
    if len(_cache) >= 200:
        for k in sorted(_cache, key=lambda k: _cache[k][0])[:50]:
            del _cache[k]
    _cache[key] = (time.monotonic(), data)

# ── Core search logic (shared by both endpoints, no rate-limit dependency) ────

async def _do_search(query: str, stores: str, max_results: int) -> dict:
    selected = sorted({s.strip() for s in stores.split(",") if s.strip() in SCRAPERS})
    if not selected:
        return {"query": query, "count": 0, "results": [], "errors": []}

    cache_key = (query.lower().strip(), tuple(selected), max_results)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    results_per_store = await asyncio.gather(
        *[SCRAPERS[s].search(query, max_results) for s in selected],
        return_exceptions=True,
    )

    combined, errors = [], []
    for store_id, result in zip(selected, results_per_store):
        if isinstance(result, MercadoLibreNotConfiguredError):
            errors.append({"store": store_id, "error": str(result), "code": "not_configured"})
        elif isinstance(result, Exception):
            errors.append({"store": store_id, "error": str(result)})
        else:
            combined.extend([p.to_dict() for p in result])

    combined.sort(key=lambda p: p["price"] if p["price"] is not None else float("inf"))

    result = {"query": query, "count": len(combined), "results": combined, "errors": errors}
    _cache_set(cache_key, result)
    return result

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/api/stores")
async def list_stores():
    return [
        {"id": "easy", "name": "Easy", "url": "https://www.easy.cl", "configured": True},
        {"id": "homecenter", "name": "Homecenter", "url": "https://www.homecenter.cl", "configured": True},
        {"id": "construmart", "name": "Construmart", "url": "https://www.construmart.cl", "configured": True},
        {"id": "imperial", "name": "Imperial", "url": "https://www.imperial.cl", "configured": True},
        {
            "id": "mercadolibre",
            "name": "MercadoLibre",
            "url": "https://www.mercadolibre.cl",
            "configured": _ml_scraper.is_configured,
        },
    ]


@app.get("/api/search")
@limiter.limit("20/minute")
async def search(
    request: Request,
    query: str = Query(..., min_length=1, max_length=200),
    stores: str = Query(default="easy,homecenter,construmart"),
    max_results: int = Query(default=10, ge=1, le=MAX_RESULTS),
):
    return await _do_search(query, stores, max_results)


@app.post("/api/search-batch")
@limiter.limit("5/minute")
async def search_batch(
    request: Request,
    file: UploadFile = File(...),
    stores: str = Form(default="easy,homecenter,construmart"),
    max_results: int = Form(default=5, ge=1, le=MAX_RESULTS),
):
    content = await file.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="Archivo demasiado grande (máx. 100 KB)")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    queries = [row[0].strip() for row in reader if row and row[0].strip()]
    queries = [q for q in queries if not q.lower().startswith("producto")]
    queries = queries[:30]

    if not queries:
        raise HTTPException(status_code=400, detail="El archivo CSV no contiene productos")

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()
        sem = asyncio.Semaphore(3)
        total = len(queries)

        async def run_one(q: str) -> None:
            try:
                async with sem:
                    result = await _do_search(q, stores, max_results)
            except Exception as exc:
                result = {"query": q, "count": 0, "results": [], "errors": [{"error": str(exc)}]}
            await queue.put((q, result))

        tasks = [asyncio.create_task(run_one(q)) for q in queries]

        completed = 0
        while completed < total:
            q, result = await queue.get()
            completed += 1
            payload = json.dumps(
                {"progress": completed, "total": total, "query": q, "result": result},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

        await asyncio.gather(*tasks, return_exceptions=True)
        yield 'data: {"done": true}\n\n'

    return StreamingResponse(generate(), media_type="text/event-stream")
