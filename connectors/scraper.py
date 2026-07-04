"""スクレイピング共通基盤（Tier2・設計書 3.3）

技術ルール:
- 実装前に各サイトの利用規約を必ず確認する（コードは robots.txt を自動チェック）
- robots.txt で禁止されている場合は取得せず、Tier3（URL生成＋目視）へフォールバック
- リクエスト間隔は最低でも数秒空ける
- User-Agent を偽装しない / ログインが必要なページは対象外
- 検索結果の1ページ目のみ取得し、アクセス数を最小限に抑える
- 取得データは私的なリサーチ用途に限定
"""
from __future__ import annotations

import logging
import urllib.robotparser
from abc import abstractmethod
from urllib.parse import urlparse

from connectors.base import BaseConnector, ConnectorError
from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)

USER_AGENT = "sedori-tool/1.0 (personal research; contact via local user)"


class ScraperConnector(BaseConnector):
    """Tier2スクレイピングの共通基盤。

    HTML構造変更で取得不能になった場合は空リストを返し、
    呼び出し側（main.py）が検索URL（Tier3相当）へフォールバックする。
    """

    tier = 2
    min_interval = 5.0  # 最低でも数秒空ける（設計書 3.3）

    def __init__(self, config: dict):
        super().__init__(config)
        self.session.headers["User-Agent"] = USER_AGENT
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    # ------------------------------------------------------------------
    @abstractmethod
    def search_url(self, query: SearchQuery) -> str:
        """検索結果1ページ目のURL"""

    @abstractmethod
    def parse(self, html: str, query: SearchQuery) -> list[Product]:
        """検索結果HTMLを共通商品モデルへ変換"""

    # ------------------------------------------------------------------
    def search(self, query: SearchQuery) -> list[Product]:
        url = self.search_url(query)
        if not self._robots_allowed(url):
            raise ConnectorError(
                f"[{self.name}] robots.txt がクロールを許可していないため取得しません。"
                "検索URL（目視確認）を利用してください"
            )
        resp = self._get(url)
        if not resp.ok:
            raise ConnectorError(f"[{self.name}] HTTP {resp.status_code}")
        products = self.parse(resp.text, query)
        if not products:
            logger.warning(
                "[%s] 商品を抽出できませんでした（HTML構造が変わった可能性）。"
                "検索URLで目視確認してください", self.name,
            )
        return products

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] robots.txt 取得失敗（安全側で取得中止）: %s", self.name, exc)
                rp.disallow_all = True
            self._robots_cache[base] = rp
        return self._robots_cache[base].can_fetch(USER_AGENT, url)
