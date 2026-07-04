"""eBay Browse API（Tier1・公式）

https://developer.ebay.com/api-docs/buy/browse/overview.html
- eBay Developer登録が必要（EBAY_CLIENT_ID / EBAY_CLIENT_SECRET）
- Client Credentials フローでアプリケーショントークンを取得
- USD→JPY換算＋輸入諸経費の概算を付与（設計書 4.6）
"""
from __future__ import annotations

import base64
import logging
import os
import time

from connectors.base import BaseConnector, ConnectorError
from core.exchange import ExchangeRates
from core.import_cost import estimate_import_cost
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


class EbayConnector(BaseConnector):
    name = "ebay"
    tier = 1
    min_interval = 0.5

    def __init__(self, config: dict, exchange: ExchangeRates | None = None):
        super().__init__(config)
        self.exchange = exchange or ExchangeRates(config)
        self._token: str | None = None
        self._token_expiry = 0.0

    def available(self) -> bool:
        return bool(os.getenv("EBAY_CLIENT_ID") and os.getenv("EBAY_CLIENT_SECRET"))

    def search(self, query: SearchQuery) -> list[Product]:
        params = {
            "q": query.query_text,
            "limit": min(query.max_results, 50),
        }
        if query.condition == "new":
            params["filter"] = "conditions:{NEW}"
        elif query.condition == "used":
            params["filter"] = "conditions:{USED}"

        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        }
        data = self._get_json(SEARCH_URL, params=params, headers=headers)
        summaries = data.get("itemSummaries", [])

        products: list[Product] = []
        for item in summaries:
            try:
                products.append(self._to_product(item, query))
            except Exception as exc:  # noqa: BLE001
                logger.debug("[ebay] 商品変換スキップ: %s", exc)
        return products

    def _to_product(self, item: dict, query: SearchQuery) -> Product:
        price_info = item.get("price") or {}
        value = float(price_info["value"])
        currency = price_info.get("currency", "USD")
        price_jpy, note = self.exchange.to_jpy(value, currency)

        shipping_jpy = 0
        options = item.get("shippingOptions") or []
        if options:
            cost = options[0].get("shippingCost") or {}
            if cost.get("value"):
                shipping_jpy, _ = self.exchange.to_jpy(
                    float(cost["value"]), cost.get("currency", currency)
                )

        condition = (item.get("condition") or "unknown").lower()
        if "new" in condition:
            condition = "new"
        elif "used" in condition or "pre-owned" in condition:
            condition = "used"

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=item.get("itemId", ""),
            title=item.get("title", ""),
            url=item.get("itemWebUrl", ""),
            image_url=(item.get("image") or {}).get("imageUrl"),
            jan_code=query.jan_code,
            price=price_jpy,
            shipping_cost=shipping_jpy,
            condition=condition,
            is_import=True,
            import_cost=estimate_import_cost(price_jpy, self.config),
            currency_note=note,
        )

    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        cred = f"{os.getenv('EBAY_CLIENT_ID')}:{os.getenv('EBAY_CLIENT_SECRET')}"
        basic = base64.b64encode(cred.encode()).decode()
        resp = self.session.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=15,
        )
        if not resp.ok:
            raise ConnectorError(f"[ebay] トークン取得失敗: HTTP {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + int(data.get("expires_in", 7200))
        return self._token
