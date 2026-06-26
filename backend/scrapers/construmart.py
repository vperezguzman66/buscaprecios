import asyncio
import json
import re
import httpx
from .base import BaseScraper, Product

_GRAPHQL_URL = "https://www.construmart.cl/graphql"
_BASE_URL = "https://www.construmart.cl"

_SEARCH_QUERY = """
query SearchProducts($q: String!, $pageSize: Int!) {
  products(search: $q, pageSize: $pageSize, currentPage: 1) {
    total_count
    items {
      name
      sku
      url_key
      stock_status
      small_image { url }
    }
  }
}
"""


async def _fetch_price(
    client: httpx.AsyncClient,
    url_key: str,
    headers: dict,
    sem: asyncio.Semaphore,
) -> tuple[float | None, str]:
    async with sem:
        try:
            resp = await client.get(f"{_BASE_URL}/{url_key}", headers=headers)
            ld_blocks = re.findall(
                r'application/ld\+json[^>]*>(.*?)</script>', resp.text, re.DOTALL
            )
            for block in ld_blocks:
                if '"price"' in block:
                    d = json.loads(block)
                    raw = d.get("offers", {}).get("price")
                    if raw:
                        value = float(str(raw).replace(",", "."))
                        return value, f"${int(value):,}".replace(",", ".")
        except Exception:
            pass
    return None, "Sin precio"


class ConstrumartScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {**self.HEADERS, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    _GRAPHQL_URL,
                    json={"query": _SEARCH_QUERY, "variables": {"q": query, "pageSize": max_results}},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        try:
            items = data["data"]["products"]["items"]
        except (KeyError, TypeError):
            return []

        if not items:
            return []

        page_headers = {**self.HEADERS, "Accept": "text/html,*/*"}
        # Limit concurrent page fetches to avoid hammering Construmart
        sem = asyncio.Semaphore(5)
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            prices = await asyncio.gather(
                *[_fetch_price(client, it["url_key"], page_headers, sem) for it in items]
            )

        products = []
        for item, (price, price_text) in zip(items, prices):
            products.append(
                Product(
                    name=item["name"],
                    price=price,
                    price_text=price_text,
                    url=f"{_BASE_URL}/{item['url_key']}",
                    image=item.get("small_image", {}).get("url"),
                    store="Construmart",
                    store_id="construmart",
                    sku=item.get("sku"),
                )
            )

        return products
