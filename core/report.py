"""候補行の組み立て（損益仮計算 → 判定 → フラグ → 出力用データ）

設計書 7.2 の処理シーケンス 4〜6 を担う:
- 実質仕入れ価格を計算
- 推定販売価格で損益を仮計算し、判定・フラグ付け
- 有望候補（△以上・要目視）にメルカリ売り切れ検索URLを付与
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from core import judge as judge_mod
from core.pricing import PriceEstimate, PriceEstimator
from core.profit import ProfitResult, calc_profit, effective_cost
from core.shipping import ShippingTable
from core.url_builder import mercari_soldout_url
from models.product import Product


@dataclass
class CandidateRow:
    product: Product
    estimate: PriceEstimate
    size_key: str
    profit: Optional[ProfitResult]  # 推定不能なら None
    judgement: str
    flags: list[str] = field(default_factory=list)
    mercari_url: str = ""

    @property
    def sort_key(self) -> tuple:
        order = judge_mod.JUDGE_ORDER.get(self.judgement, 9)
        profit = self.profit.profit if self.profit else 0
        return (order, -profit)


def build_rows(products: list[Product], config: dict) -> list[CandidateRow]:
    estimator = PriceEstimator(config)
    shipping_table = ShippingTable(config)
    include_points = bool(config.get("points", {}).get("include_as_discount", True))
    default_size = config.get("pricing", {}).get("default_size", "size60")
    entry = shipping_table.get(default_size)
    fee_rate = float(config.get("mercari", {}).get("fee_rate", 0.10))

    rows: list[CandidateRow] = []
    for product in products:
        estimate = estimator.estimate(product, products)
        cost = effective_cost(product, include_points=include_points)

        profit_result: Optional[ProfitResult] = None
        if estimate.estimated_price:
            profit_result = calc_profit(
                sell_price=estimate.estimated_price,
                cost=cost,
                fee_rate=fee_rate,
                shipping_out=entry.shipping,
                material=entry.material,
            )

        judgement = judge_mod.judge(profit_result, config, is_import=product.is_import)
        row_flags = judge_mod.flags(
            product, profit_result, config,
            estimate_status=estimate.status, size_key=default_size,
        )

        # 有望候補（×以外）にメルカリ売り切れ検索URLを付与（設計書 3.4-②）
        mercari_url = ""
        if judgement != judge_mod.JUDGE_SKIP:
            query = product.jan_code or product.title[:40]
            mercari_url = mercari_soldout_url(query, config)

        rows.append(CandidateRow(
            product=product,
            estimate=estimate,
            size_key=default_size,
            profit=profit_result,
            judgement=judgement,
            flags=row_flags,
            mercari_url=mercari_url,
        ))

    rows.sort(key=lambda r: r.sort_key)
    return rows


def filter_rows(rows: list[CandidateRow], config: dict) -> list[CandidateRow]:
    """×見送りを出力から除外する設定（output.skip_rejected）に対応"""
    if config.get("output", {}).get("skip_rejected", False):
        return [r for r in rows if r.judgement != judge_mod.JUDGE_SKIP]
    return rows


def dedupe_products(products: list[Product]) -> list[Product]:
    """URL基準の重複排除（設計書 6.3）"""
    seen: set[str] = set()
    unique: list[Product] = []
    for p in products:
        if p.url and p.url not in seen:
            seen.add(p.url)
            unique.append(p)
    return unique
