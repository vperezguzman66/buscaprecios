import json
import re
import httpx
from .base import BaseScraper, Product

# Homecenter Chile is operated by Sodimac
_SEARCH_BASE = "https://sodimac.cl/sodimac-cl/buscar"


def _parse_cl_price(price_str: str) -> float | None:
    clean = re.sub(r"[^\d]", "", price_str or "")
    return float(clean) if clean else None


_PRICE_PRIORITY = ["eventPrice", "internetPrice", "offerPrice", "cmrPrice", "normalPrice"]


def _best_price(prices: list[dict]) -> tuple[float | None, str]:
    candidates: dict[str, float] = {}
    for p in prices:
        if p.get("crossed"):
            continue
        price_type = p.get("type", "")
        price_list = p.get("price", [])
        if price_list:
            val = _parse_cl_price(price_list[0])
            if val:
                candidates[price_type] = val

    for price_type in _PRICE_PRIORITY:
        value = candidates.get(price_type)
        if value:
            return value, f"${int(value):,}".replace(",", ".")
    return None, "Sin precio"


class HomecenterScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {**self.HEADERS, "Accept": "text/html,application/xhtml+xml,*/*"}
        try:
            # Pass query as a param so httpx handles encoding automatically
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                resp = await client.get(
                    _SEARCH_BASE,
                    params={"Ntt": query},
                    headers=headers,
                )
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
            raw_products = data["props"]["pageProps"].get("results", [])
        except (KeyError, json.JSONDecodeError):
            return []

        products = []
        for p in raw_products[:max_results]:
            try:
                price, price_text = _best_price(p.get("prices", []))
                image = (p.get("mediaUrls") or [None])[0]

                products.append(
                    Product(
                        name=p["displayName"],
                        price=price,
                        price_text=price_text,
                        url=p.get("url", ""),
                        image=image,
                        store="Homecenter (Sodimac)",
                        store_id="homecenter",
                        sku=p.get("skuId") or p.get("productId"),
                    )
                )
            except (KeyError, TypeError):
                continue

        return products
