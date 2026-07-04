"""Amazon PA-API v5（Tier1・公式）

- アソシエイト登録＋売上実績が必要なため Phase 3 の位置づけ（設計書 10章）
- `python-amazon-paapi` がインストールされ、キーが設定されている場合のみ有効
"""
from __future__ import annotations

import logging
import os

from connectors.base import BaseConnector, ConnectorError
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

try:
    from amazon_paapi import AmazonApi  # type: ignore
    _PAAPI_AVAILABLE = True
except ImportError:
    _PAAPI_AVAILABLE = False


class AmazonConnector(BaseConnector):
    name = "amazon"
    tier = 1
    min_interval = 1.5  # PA-APIはレート制限が厳しい

    def available(self) -> bool:
        return _PAAPI_AVAILABLE and all(
            os.getenv(k) for k in ("AMAZON_ACCESS_KEY", "AMAZON_SECRET_KEY", "AMAZON_PARTNER_TAG")
        )

    def search(self, query: SearchQuery) -> list[Product]:
        if not _PAAPI_AVAILABLE:
            raise ConnectorError(
                "[amazon] python-amazon-paapi が未インストールです"
                "（pip install python-amazon-paapi）"
            )
        self._throttle()
        api = AmazonApi(
            os.getenv("AMAZON_ACCESS_KEY"),
            os.getenv("AMAZON_SECRET_KEY"),
            os.getenv("AMAZON_PARTNER_TAG"),
            "JP",
        )
        try:
            result = api.search_items(
                keywords=query.query_text,
                item_count=min(query.max_results, 10),
            )
        except Exception as exc:  # noqa: BLE001
            raise ConnectorError(f"[amazon] PA-API検索失敗: {exc}") from exc

        products: list[Product] = []
        for item in getattr(result, "items", []) or []:
            try:
                products.append(self._to_product(item, query))
            except Exception as exc:  # noqa: BLE001
                logger.debug("[amazon] 商品変換スキップ: %s", exc)
        return products

    def _to_product(self, item, query: SearchQuery) -> Product:
        title = item.item_info.title.display_value
        listing = item.offers.listings[0]
        price = int(listing.price.amount)
        condition = "new"
        cond = getattr(listing, "condition", None)
        if cond and getattr(cond, "value", "") and cond.value.lower() != "new":
            condition = "used"
        image = None
        if getattr(item, "images", None) and item.images.primary:
            image = item.images.primary.medium.url

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=item.asin,
            title=title,
            url=item.detail_page_url,
            image_url=image,
            jan_code=query.jan_code,
            price=price,
            shipping_cost=0,
            condition=condition,
        )
