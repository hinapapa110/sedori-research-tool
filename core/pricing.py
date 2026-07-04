"""想定販売価格の自動推定モジュール（設計書 3.4-① / 4.5）

楽天/Yahoo!の同一商品（JAN一致）の相場中央値 × 補正係数 → メルカリ想定販売価格

- 中央値を採用（平均値は外れ値に弱い）
- 推定ステータス: 推定OK（3件以上）/ 参考値（1〜2件）/ 推定不能（0件）
- 推定値はあくまで足切り用。仕入れ判断は目視確定後の値で行う
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional

from models.product import Product

STATUS_OK = "推定OK"
STATUS_REF = "参考値"
STATUS_NONE = "推定不能"


@dataclass(frozen=True)
class PriceEstimate:
    estimated_price: Optional[int]  # 推定販売価格（円）。推定不能なら None
    status: str                     # 推定OK / 参考値 / 推定不能
    sample_count: int
    reference_median: Optional[int]


class PriceEstimator:
    def __init__(self, config: dict):
        pricing = config.get("pricing", {})
        self.reference_sites: list[str] = pricing.get("reference_sites", ["rakuten", "yahoo"])
        self.adjust_factor: float = float(pricing.get("adjust_factor", 0.85))
        self.min_samples_ok: int = int(pricing.get("min_samples_ok", 3))

    def estimate(self, candidate: Product, all_products: list[Product]) -> PriceEstimate:
        """候補商品の想定販売価格を推定する。

        参照プール: 参照サイト（楽天/Yahoo!）の商品のうち、候補とJANが一致し、
        候補自身ではなく、同等状態（中古なら中古）のもの。
        """
        samples = self._collect_samples(candidate, all_products)
        if not samples:
            return PriceEstimate(None, STATUS_NONE, 0, None)

        median = int(round(statistics.median(samples)))
        estimated = int(round(median * self.adjust_factor))
        status = STATUS_OK if len(samples) >= self.min_samples_ok else STATUS_REF
        return PriceEstimate(estimated, status, len(samples), median)

    def _collect_samples(self, candidate: Product, all_products: list[Product]) -> list[int]:
        if not candidate.jan_code:
            return []
        target_condition = candidate.condition if candidate.condition in ("new", "used") else None
        pool = [
            p for p in all_products
            if p.source in self.reference_sites
            and p.jan_code == candidate.jan_code
            and p.url != candidate.url
            and p.price > 0
        ]
        if target_condition:
            same = [p for p in pool if p.condition == target_condition]
            # 同等状態のサンプルが1件でもあればそちらを優先
            if same:
                pool = same
        return [p.price for p in pool]
