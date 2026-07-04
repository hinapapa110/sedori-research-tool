"""楽天市場商品検索API（Tier1・公式・無料）

https://webservice.rakuten.co.jp/documentation/ichiba-item-search
- 楽天デベロッパー登録のみで利用可
- 認証は applicationId（アプリケーションID）と accessKey（アクセスキー）の
  両方が必須（新方式）。RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY を .env に設定する
- レート制限: 1秒1リクエスト目安
"""
from __future__ import annotations

import logging
import os

from connectors.base import BaseConnector
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

# 新認証方式（applicationId + accessKey）用エンドポイント。
# 利用にはアプリの「許可されたWebサイト」に実行元のグローバルIP（/32形式）の登録が必要
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"


class RakutenConnector(BaseConnector):
    name = "rakuten"
    tier = 1
    min_interval = 1.0

    def available(self) -> bool:
        return bool(os.getenv("RAKUTEN_APP_ID") and os.getenv("RAKUTEN_ACCESS_KEY"))

    def search(self, query: SearchQuery) -> list[Product]:
        keyword = query.query_text
        # 楽天APIには中古絞り込みがないため、キーワードで擬似的に絞る
        if query.condition == "used" and not query.jan_code:
            keyword = f"{keyword} 中古"

        params = {
            "applicationId": os.getenv("RAKUTEN_APP_ID"),
            "accessKey": os.getenv("RAKUTEN_ACCESS_KEY"),
            "keyword": keyword,
            "hits": min(query.max_results, 30),
            "sort": "+itemPrice",
            "formatVersion": 2,
        }
        data = self._get_json(ENDPOINT, params=params)
        items = data.get("Items", [])

        products: list[Product] = []
        for item in items:
            # formatVersion=2 ではフラット、1 では {"Item": {...}} 形式
            if "Item" in item:
                item = item["Item"]
            try:
                products.append(self._to_product(item, query))
            except Exception as exc:  # noqa: BLE001 - 1件の変換失敗で全体を止めない
                logger.debug("[rakuten] 商品変換スキップ: %s", exc)
        return products

    def _to_product(self, item: dict, query: SearchQuery) -> Product:
        price = int(item["itemPrice"])
        point_rate = int(item.get("pointRate", 1) or 1)
        # postageFlag: 0=送料込み / 1=送料別（別の場合は金額不明のため0円+要確認）
        shipping = 0
        image_urls = item.get("mediumImageUrls") or []
        image = None
        if image_urls:
            first = image_urls[0]
            image = first.get("imageUrl") if isinstance(first, dict) else first

        title = item.get("itemName", "")
        condition = "used" if "中古" in title else ("new" if "新品" in title else "unknown")

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=item.get("itemCode", ""),
            title=title,
            url=item.get("itemUrl", ""),
            image_url=image,
            jan_code=query.jan_code,  # 楽天APIはJANを返さないため検索条件を引き継ぐ
            price=price,
            shipping_cost=shipping,
            condition=condition,
            points=price * point_rate // 100,
        )
