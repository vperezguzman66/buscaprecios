import asyncio
import re
import httpx
from .base import BaseScraper, Product

_ASSEMBLER_URL = "https://www.imperial.cl/ccstore/v1/assembler/pages/Default/services/guidedsearch"
_PRODUCTS_URL = "https://www.imperial.cl/ccstore/v1/products"
_CATEGORY_URL = "https://www.imperial.cl/ccstorex/custom/occ/get-category-products"
_BASE_URL = "https://www.imperial.cl"


def _parse_price(value: str | None) -> tuple[float | None, str]:
    if not value:
        return None, "Sin precio"
    try:
        price = float(value)
        return price, f"${int(price):,}".replace(",", ".")
    except (ValueError, TypeError):
        return None, "Sin precio"


def _extract_category_id(url: str) -> str | None:
    m = re.search(r"/category/(\w+)", url)
    return m.group(1) if m else None


class ImperialScraper(BaseScraper):
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        headers = {**self.HEADERS, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    _ASSEMBLER_URL,
                    params={"Ntt": query, "Nrpp": max_results},
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            return []

        # Redirect to category: fetch products via category endpoint
        if "endeca:redirect" in data:
            redirect_url = data["endeca:redirect"]["link"]["url"]
            category_id = _extract_category_id(redirect_url)
            if not category_id:
                return []
            return await self._from_category(category_id, max_results, headers)

        records = data.get("resultsList", {}).get("records", [])
        return await self._parse_records(records, max_results, headers)

    async def _from_category(
        self, category_id: str, max_results: int, headers: dict
    ) -> list[Product]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    _CATEGORY_URL,
                    params={
                        "priceListGroupId": "_default_price_book",
                        "categoryId": category_id,
                        "limit": max_results,
                        "offset": 0,
                        "fields": "id",
                        "sort": "listPrice:asc",
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                ids_data = resp.json()
        except Exception:
            return []

        product_ids = [str(item) for item in (ids_data if isinstance(ids_data, list) else [])]
        if not product_ids:
            return []

        return await self._fetch_routes_and_build(product_ids, prices={}, names={}, images={}, headers=headers)

    async def _parse_records(
        self, records: list, max_results: int, headers: dict
    ) -> list[Product]:
        prices: dict[str, tuple[float | None, str]] = {}
        names: dict[str, str] = {}
        images: dict[str, str] = {}
        product_ids: list[str] = []

        for r in records[:max_results]:
            inner = r.get("records", [{}])[0]
            attrs = inner.get("attributes", {})
            sku_id = (attrs.get("sku.repositoryId") or [None])[0]
            if not sku_id:
                continue
            product_ids.append(sku_id)
            prices[sku_id] = _parse_price((attrs.get("sku.activePrice") or [None])[0])
            names[sku_id] = (attrs.get("product.longDescription") or [sku_id])[0]
            img = (attrs.get("product.primaryFullImageURL") or [None])[0]
            images[sku_id] = f"{_BASE_URL}{img}" if img else None

        if not product_ids:
            return []

        return await self._fetch_routes_and_build(product_ids, prices, names, images, headers)

    async def _fetch_routes_and_build(
        self,
        product_ids: list[str],
        prices: dict,
        names: dict,
        images: dict,
        headers: dict,
    ) -> list[Product]:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    _PRODUCTS_URL,
                    params={
                        "productIds": ",".join(product_ids),
                        "storePriceListGroupId": "_default_price_book",
                        "fields": "id,route,displayName,primaryFullImageURL",
                    },
                    headers=headers,
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
        except Exception:
            items = []

        products = []
        for item in items:
            pid = item.get("id")
            route = item.get("route", "")
            price, price_text = prices.get(pid, (None, "Sin precio"))
            name = names.get(pid) or item.get("displayName", pid)
            img = images.get(pid)
            if img is None:
                raw_img = item.get("primaryFullImageURL")
                img = f"{_BASE_URL}{raw_img}" if raw_img else None

            products.append(Product(
                name=name,
                price=price,
                price_text=price_text,
                url=f"{_BASE_URL}{route}" if route else _BASE_URL,
                image=img,
                store="Imperial",
                store_id="imperial",
                sku=pid,
            ))

        return products
