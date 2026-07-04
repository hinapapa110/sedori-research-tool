"""コネクタ共通インターフェース（設計書 3.2 / 9章）"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models.product import Product, SearchQuery

logger = logging.getLogger(__name__)


class ConnectorError(Exception):
    """コネクタ内の回復不能なエラー（該当サイトのみスキップして継続）"""


class BaseConnector(ABC):
    """全コネクタの基底クラス。

    - レート制限: min_interval 秒以上の間隔を保証（サイトごとに設定）
    - リトライ: 通信エラー時は指数バックオフで最大3回（設計書 9章）
    """

    name: str = "base"
    tier: int = 1
    min_interval: float = 1.0  # 楽天は1秒/回が目安（設計書 3.1）

    def __init__(self, config: dict):
        self.config = config
        self._lock = threading.Lock()
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "sedori-tool/1.0 (personal research)"

    # ------------------------------------------------------------------
    @abstractmethod
    def search(self, query: SearchQuery) -> list[Product]:
        """キーワード/JAN/型番で検索し、共通商品モデルで返す"""

    def available(self) -> bool:
        """APIキー等が揃っていて利用可能か。不可ならスキップして継続"""
        return True

    # ------------------------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()

    @retry(
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _get(self, url: str, *, params: dict | None = None, headers: dict | None = None,
             timeout: int = 15) -> requests.Response:
        self._throttle()
        resp = self.session.get(url, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            # レート制限: 一呼吸置いて tenacity に再試行させる
            logger.warning("[%s] レート制限(429)。待機して再試行します", self.name)
            time.sleep(5)
            raise requests.ConnectionError("rate limited (429)")
        return resp

    def _get_json(self, url: str, *, params: dict | None = None,
                  headers: dict | None = None) -> dict:
        resp = self._get(url, params=params, headers=headers)
        if resp.status_code in (401, 403):
            raise ConnectorError(
                f"[{self.name}] APIキーが無効か権限がありません (HTTP {resp.status_code})。"
                " .env の設定を確認してください"
            )
        if not resp.ok:
            raise ConnectorError(f"[{self.name}] APIエラー: HTTP {resp.status_code} {resp.text[:200]}")
        return resp.json()
