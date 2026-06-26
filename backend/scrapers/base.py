from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Product:
    name: str
    price: float | None
    price_text: str
    url: str
    image: str | None
    store: str
    store_id: str
    sku: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "price": self.price,
            "price_text": self.price_text,
            "url": self.url,
            "image": self.image,
            "store": self.store,
            "store_id": self.store_id,
            "sku": self.sku,
        }


class BaseScraper(ABC):
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "es-CL,es;q=0.9",
        "Accept": "application/json, text/html, */*",
    }

    @abstractmethod
    async def search(self, query: str, max_results: int = 10) -> list[Product]:
        pass
