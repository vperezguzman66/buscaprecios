import asyncio
import os
import time
import httpx
from .base import BaseScraper, Product

_TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
_SEARCH_URL = "https://api.mercadolibre.com/sites/MLC/search"


class MercadoLibreNotConfiguredError(Exception):
    pass


class MercadoLibreScraper(BaseScraper):
    def __init__(self):
        self._client_id = os.getenv("ML_CLIENT_ID", "")
        self._client_secret = os.getenv("ML_CLIENT_SECRET", "")
        self._token: str | None = None
        self._token_expires: float = 0
        self._token_lock = asyncio.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _token_valid(self) -> bool:
        return bool(self._token and time.time() < self._token_expires - 60)

    async def _get_token(self) -> str:
        if not self.is_configured:
            raise MercadoLibreNotConfiguredError(
                "Faltan credenciales ML_CLIENT_ID / ML_CLIENT_SECRET. "
                "Regístralas en https://developers.mercadolibre.com"
            )
        if self._token_valid():
            return self._token

        async with self._token_lock:
            # Another coroutine may have refreshed while we waited for the lock
            if self._token_valid():
                return self._token

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    _TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            self._token = data["access_token"]
            self._token_expires = time.time() + data.get("expires_in", 21600)
            return self._token

    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        token = await self._get_token()

        params = {
            "q": query,
            "limit": min(max_results, 50),
            "offset": 0,
            "condition": "new",
        }
        headers = {**self.HEADERS, "Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        products = []
        for item in data.get("results", []):
            price = item.get("price")
            if price:
                price_text = f"${int(price):,}".replace(",", ".")
            else:
                price_text = "Sin precio"

            products.append(
                Product(
                    name=item["title"],
                    price=float(price) if price else None,
                    price_text=price_text,
                    url=item.get("permalink", ""),
                    image=item.get("thumbnail", "").replace("I.jpg", "O.jpg"),
                    store="MercadoLibre",
                    store_id="mercadolibre",
                    sku=item.get("id"),
                )
            )

        return products
