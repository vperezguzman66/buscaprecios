import json
import re
import urllib.parse
import httpx
from .base import BaseScraper, Product

_SEARCH_URL = "https://www.easy.cl/search/{query}"
_BASE_URL = "https://www.easy.cl"


def _parse_cl_price(value: float | None) -> tuple[float | None, str]:
    if not value:
        return None, "Sin precio"
    return float(value), f"${int(value):,}".replace(",", ".")


class EasyScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        slug = urllib.parse.quote(query.replace(" ", "-"), safe="-")
        url = _SEARCH_URL.format(query=slug)
        headers = {**self.HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                html = resp.text
        except Exception:
            return []

        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            html, re.DOTALL
        )
        if not match:
            return []

        try:
            data = json.loads(match.group(1))
            pp = data["props"]["pageProps"]
            raw_products = pp.get("serverProductsResponse", {}).get("productList", [])
        except (KeyError, json.JSONDecodeError):
            return []

        products = []
        for p in raw_products[:max_results]:
            try:
                prices = p.get("prices", {}) or {}
                price_val = prices.get("offerPrice") or prices.get("normalPrice")
                price, price_text = _parse_cl_price(price_val)

                link_text = p.get("linkText", "")
                if link_text and not link_text.startswith("http"):
                    product_url = f"{_BASE_URL}/{link_text}"
                else:
                    product_url = link_text

                products.append(
                    Product(
                        name=p["productName"],
                        price=price,
                        price_text=price_text,
                        url=product_url,
                        image=p.get("imageUrl"),
                        store="Easy",
                        store_id="easy",
                        sku=p.get("sku"),
                    )
                )
            except (KeyError, TypeError):
                continue

        return products
