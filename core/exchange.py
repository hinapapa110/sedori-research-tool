"""為替レート取得（設計書 4.6 / 9章）

- 無料為替API（open.er-api.com）から自動取得
- 取得失敗時は config.yaml の固定レートにフォールバック
- 円安リスク吸収のため為替バッファ（デフォルト+3%）を上乗せ
"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://open.er-api.com/v6/latest/{base}"


class ExchangeRates:
    def __init__(self, config: dict):
        self._imp = config.get("import", {})
        self._buffer = float(self._imp.get("exchange_buffer", 0.03))
        self._fallback: dict = self._imp.get("fallback_rates", {"USD": 155.0, "CNY": 22.0})
        self._cache: dict[str, float] = {}

    def rate_to_jpy(self, currency: str) -> float:
        """1単位あたりの円レート（為替バッファ込み）"""
        currency = currency.upper()
        if currency == "JPY":
            return 1.0
        if currency not in self._cache:
            self._cache[currency] = self._fetch(currency)
        return self._cache[currency] * (1.0 + self._buffer)

    def raw_rate(self, currency: str) -> float:
        """バッファなしの生レート（表示用）"""
        currency = currency.upper()
        if currency == "JPY":
            return 1.0
        if currency not in self._cache:
            self._cache[currency] = self._fetch(currency)
        return self._cache[currency]

    def _fetch(self, currency: str) -> float:
        try:
            resp = requests.get(_API_URL.format(base=currency), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            rate = float(data["rates"]["JPY"])
            logger.info("為替レート取得: 1 %s = %.2f JPY", currency, rate)
            return rate
        except Exception as exc:  # noqa: BLE001 - フォールバックで継続（設計書9章）
            fallback = float(self._fallback.get(currency, 0.0))
            if fallback <= 0:
                raise RuntimeError(
                    f"為替レート取得に失敗し、config.yaml にも {currency} の固定レートがありません"
                ) from exc
            logger.warning("為替API失敗（%s）。固定レート %s を使用: %s", currency, fallback, exc)
            return fallback

    def to_jpy(self, amount: float, currency: str) -> tuple[int, str]:
        """外貨→円換算。 (円額, 換算メモ) を返す。メモ例: "USD 12.50 @150.2(+3%)" """
        rate = self.rate_to_jpy(currency)
        raw = self.raw_rate(currency)
        jpy = int(round(amount * rate))
        note = f"{currency.upper()} {amount:.2f} @{raw:.1f}(+{self._buffer:.0%})"
        return jpy, note
