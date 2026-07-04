"""Yahoo!ショッピング商品検索API V3（Tier1・公式・無料）

https://developer.yahoo.co.jp/webapi/shopping/v3/itemsearch.html
- Yahoo!デベロッパー登録のみで利用可（YAHOO_APP_ID / Client ID）
"""
from __future__ import annotations

import logging
import os

from connectors.base import BaseConnector
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

ENDPOINT = "https://shopping.yahooapis.jp/ShoppingWebService/V3/itemSearch"


class YahooConnector(BaseConnector):
    name = "yahoo"
    tier = 1
    min_interval = 1.0

    def available(self) -> bool:
        return bool(os.getenv("YAHOO_APP_ID"))

    def search(self, query: SearchQuery) -> list[Product]:
        params = {
            "appid": os.getenv("YAHOO_APP_ID"),
            "results": min(query.max_results, 50),
            "sort": "+price",
        }
        if query.jan_code:
            params["jan_code"] = query.jan_code
        else:
            params["query"] = query.query_text
        if query.condition in ("new", "used"):
            params["condition"] = query.condition

        data = self._get_json(ENDPOINT, params=params)
        hits = data.get("hits", [])

        products: list[Product] = []
        for hit in hits:
            try:
                products.append(self._to_product(hit))
            except Exception as exc:  # noqa: BLE001
                logger.debug("[yahoo] 商品変換スキップ: %s", exc)
        return products

    def _to_product(self, hit: dict) -> Product:
        price = int(hit["price"])
        point = hit.get("point") or {}
        points = int(point.get("amount", 0) or 0)
        shipping_info = hit.get("shipping") or {}
        # shipping.code: 1=送料情報なし / 2=送料無料 / 3=条件付き送料無料
        shipping = 0 if shipping_info.get("code") in (2, 3) else 0
        image = (hit.get("image") or {}).get("medium")
        condition = hit.get("condition", "unknown") or "unknown"

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=str(hit.get("code", "")),
            title=hit.get("name", ""),
            url=hit.get("url", ""),
            image_url=image,
            jan_code=hit.get("janCode") or None,
            price=price,
            shipping_cost=shipping,
            condition=condition,
            points=points,
        )
