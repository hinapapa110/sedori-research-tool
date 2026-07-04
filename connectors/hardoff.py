"""ハードオフネットモールコネクタ（Tier2・Phase 4 予定）

設計書 10章の通り Phase 4 で規約確認の上実装する。
現時点では未実装（unavailable）とし、検索URLフォールバック（Tier3扱い）で対応する。
"""
from __future__ import annotations

from connectors.scraper import ScraperConnector
from models.product import Product, SearchQuery


class HardoffConnector(ScraperConnector):
    name = "hardoff"

    def available(self) -> bool:
        return False  # Phase 4: 規約確認の上でパーサを実装するまで無効

    def search_url(self, query: SearchQuery) -> str:
        from core.url_builder import site_search_url
        return site_search_url("hardoff", query.query_text)

    def parse(self, html: str, query: SearchQuery) -> list[Product]:
        raise NotImplementedError("Phase 4 で実装予定")
