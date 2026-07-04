"""AliExpress アフィリエイトAPI（Tier1・公式）

https://openservice.aliexpress.com/ （aliexpress.affiliate.product.query）
- AliExpressアフィリエイト登録が必要（ALIEXPRESS_APP_KEY / ALIEXPRESS_APP_SECRET）
- target_currency=JPY で円建て価格を直接取得（不可時はUSD→JPY換算）
- 輸入諸経費の概算を付与（設計書 4.6）
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time

from connectors.base import BaseConnector, ConnectorError
from core.exchange import ExchangeRates
from core.import_cost import estimate_import_cost
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

ENDPOINT = "https://api-sg.aliexpress.com/sync"
METHOD = "aliexpress.affiliate.product.query"


class AliExpressConnector(BaseConnector):
    name = "aliexpress"
    tier = 1
    min_interval = 1.0

    def __init__(self, config: dict, exchange: ExchangeRates | None = None):
        super().__init__(config)
        self.exchange = exchange or ExchangeRates(config)

    def available(self) -> bool:
        return bool(os.getenv("ALIEXPRESS_APP_KEY") and os.getenv("ALIEXPRESS_APP_SECRET"))

    def search(self, query: SearchQuery) -> list[Product]:
        params = {
            "app_key": os.getenv("ALIEXPRESS_APP_KEY"),
            "method": METHOD,
            "sign_method": "sha256",
            "timestamp": str(int(time.time() * 1000)),
            "keywords": query.query_text,
            "page_size": str(min(query.max_results, 50)),
            "target_currency": "JPY",
            "target_language": "ja",
            "tracking_id": os.getenv("ALIEXPRESS_TRACKING_ID", "default"),
        }
        params["sign"] = self._sign(params)

        data = self._get_json(ENDPOINT, params=params)
        if "error_response" in data:
            raise ConnectorError(f"[aliexpress] APIエラー: {data['error_response']}")

        try:
            result = data["aliexpress_affiliate_product_query_response"]["resp_result"]["result"]
            items = result.get("products", {}).get("product", [])
        except (KeyError, TypeError):
            logger.warning("[aliexpress] 予期しないレスポンス形式: %s", str(data)[:200])
            return []

        products: list[Product] = []
        for item in items:
            try:
                products.append(self._to_product(item, query))
            except Exception as exc:  # noqa: BLE001
                logger.debug("[aliexpress] 商品変換スキップ: %s", exc)
        return products

    def _to_product(self, item: dict, query: SearchQuery) -> Product:
        currency = item.get("target_sale_price_currency", "JPY")
        value = float(item.get("target_sale_price") or item.get("sale_price"))
        if currency == "JPY":
            price_jpy = int(round(value))
            note = "AliExpress JPY建て"
        else:
            price_jpy, note = self.exchange.to_jpy(value, currency)

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=str(item.get("product_id", "")),
            title=item.get("product_title", ""),
            url=item.get("product_detail_url", ""),
            image_url=item.get("product_main_image_url"),
            jan_code=query.jan_code,
            price=price_jpy,
            shipping_cost=0,  # 商品により異なるため0仮置き（要目視）
            condition="new",
            is_import=True,
            import_cost=estimate_import_cost(price_jpy, self.config),
            currency_note=note,
        )

    @staticmethod
    def _sign(params: dict) -> str:
        """AliExpressオープンプラットフォームのHMAC-SHA256署名"""
        secret = os.getenv("ALIEXPRESS_APP_SECRET", "")
        base = "".join(f"{k}{params[k]}" for k in sorted(params))
        return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()
