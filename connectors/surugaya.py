"""駿河屋コネクタ（Tier2・スクレイピング）

- 公式APIなし。robots.txt を自動チェックし、不許可なら取得しない（設計書 3.3）
- HTML構造変更で抽出できない場合は空リスト → 検索URLフォールバック
- config.yaml で tier2_scraping_enabled: true にした場合のみ有効
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

from connectors.scraper import ScraperConnector
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

BASE_URL = "https://www.suruga-ya.jp"
_PRICE_RE = re.compile(r"([\d,]+)\s*円")


class SurugayaConnector(ScraperConnector):
    name = "surugaya"

    def search_url(self, query: SearchQuery) -> str:
        return f"{BASE_URL}/search?search_word={quote(query.query_text)}"

    def parse(self, html: str, query: SearchQuery) -> list[Product]:
        soup = BeautifulSoup(html, "html.parser")
        # HTML構造の変更に備えて複数の候補セレクタを試す
        items = (
            soup.select("div.item_box")
            or soup.select("div.item")
            or soup.select("li.item")
        )
        products: list[Product] = []
        for item in items[: query.max_results]:
            try:
                product = self._parse_item(item, query)
                if product:
                    products.append(product)
            except Exception as exc:  # noqa: BLE001
                logger.debug("[surugaya] アイテム解析スキップ: %s", exc)
        return products

    def _parse_item(self, item, query: SearchQuery) -> Product | None:
        link = item.select_one("a[href*='/product/']") or item.select_one("h3 a, .title a, a")
        if not link or not link.get("href"):
            return None
        url = urljoin(BASE_URL, link["href"])
        title = link.get_text(strip=True) or (link.get("title") or "")

        text = item.get_text(" ", strip=True)
        m = _PRICE_RE.search(text)
        if not m:
            return None
        price = int(m.group(1).replace(",", ""))

        img = item.select_one("img")
        image_url = None
        if img:
            image_url = img.get("src") or img.get("data-src")
            if image_url:
                image_url = urljoin(BASE_URL, image_url)

        condition = "new" if "新品" in text else "used"  # 駿河屋は中古が基本

        return Product(
            source=self.name,
            tier=self.tier,
            product_id=url.rstrip("/").rsplit("/", 1)[-1],
            title=title,
            url=url,
            image_url=image_url,
            jan_code=query.jan_code,
            price=price,
            shipping_cost=0,  # 一定額以上送料無料などの条件があるため0仮置き
            condition=condition,
        )
