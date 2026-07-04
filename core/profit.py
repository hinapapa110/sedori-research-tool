"""損益計算モジュール（設計書 4.1）

実質仕入れ価格 = 商品価格 + 仕入れ送料 + 輸入諸経費 - ポイント還元
販売手数料     = メルカリ想定販売価格 × 手数料率
総コスト       = 実質仕入れ価格 + 販売手数料 + 発送送料 + 資材代
利益額         = 想定販売価格 - 総コスト
利益率         = 利益額 ÷ 想定販売価格
ROI            = 利益額 ÷ 実質仕入れ価格
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from models.product import Product


@dataclass(frozen=True)
class ProfitResult:
    sell_price: int
    effective_cost: int   # 実質仕入れ価格
    fee: int              # 販売手数料
    shipping_out: int     # 発送送料
    material: int         # 資材代
    profit: int           # 利益額
    margin: Optional[float]  # 利益率（0〜1）。販売価格0なら None
    roi: Optional[float]     # ROI（0〜1）。仕入れ0円なら None


def effective_cost(product: Product, include_points: bool = True) -> int:
    """実質仕入れ価格。ポイント還元の控除は設定でON/OFF（設計書 3.5）"""
    cost = product.price + product.shipping_cost + product.import_cost
    if include_points:
        cost -= product.points
    return max(cost, 0)


def calc_profit(
    sell_price: int,
    cost: int,
    fee_rate: float,
    shipping_out: int,
    material: int,
) -> ProfitResult:
    fee = round(sell_price * fee_rate)
    profit = sell_price - cost - fee - shipping_out - material
    margin = (profit / sell_price) if sell_price > 0 else None
    roi = (profit / cost) if cost > 0 else None
    return ProfitResult(
        sell_price=sell_price,
        effective_cost=cost,
        fee=fee,
        shipping_out=shipping_out,
        material=material,
        profit=profit,
        margin=margin,
        roi=roi,
    )
