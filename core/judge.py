"""仕入れ判定モジュール（設計書 5章）"""
from __future__ import annotations

from typing import Optional

from core.profit import ProfitResult
from models.product import Product

JUDGE_STRONG = "◎"
JUDGE_BUY = "○"
JUDGE_CONSIDER = "△"
JUDGE_SKIP = "×"
JUDGE_UNKNOWN = "要目視"  # 相場推定不能で自動判定できない


def judge(result: Optional[ProfitResult], config: dict, is_import: bool = False) -> str:
    """利益額・利益率から ◎○△× を判定する。

    輸入品はリスクプレミアムとして利益率基準に上乗せ（設計書 4.6）。
    result が None（想定販売価格が推定不能）の場合は「要目視」。
    """
    if result is None or result.margin is None:
        return JUDGE_UNKNOWN

    jc = config.get("judge", {})
    add = float(config.get("import", {}).get("risk_margin_add", 0.05)) if is_import else 0.0

    tiers = [
        (JUDGE_STRONG, jc.get("strong_buy", {"profit": 1500, "margin": 0.25})),
        (JUDGE_BUY, jc.get("buy", {"profit": 800, "margin": 0.15})),
        (JUDGE_CONSIDER, jc.get("consider", {"profit": 500, "margin": 0.10})),
    ]
    for label, th in tiers:
        if result.profit >= int(th["profit"]) and result.margin >= float(th["margin"]) + add:
            return label
    return JUDGE_SKIP


def flags(
    product: Product,
    result: Optional[ProfitResult],
    config: dict,
    estimate_status: Optional[str] = None,
    size_key: str = "size60",
) -> list[str]:
    """補助フラグ（設計書 5.2）"""
    out: list[str] = []

    if size_key in ("size100", "size120"):
        out.append("大型注意")

    buy_margin = float(config.get("judge", {}).get("buy", {}).get("margin", 0.15))
    if result and result.margin is not None and result.margin >= buy_margin and 0 < result.profit <= 500:
        out.append("薄利多売")

    limit = int(config.get("limits", {}).get("max_purchase_price", 10000))
    cost = result.effective_cost if result else (product.price + product.shipping_cost + product.import_cost)
    if cost > limit:
        out.append("高額仕入れ")

    if product.currency_note:
        out.append("為替注意")
    if product.is_import:
        out.append("輸入品注意")
    if estimate_status in ("参考値", "推定不能"):
        out.append("要目視")

    return out


# 判定の並び順（スプレッドシート出力時のソート用）
JUDGE_ORDER = {JUDGE_STRONG: 0, JUDGE_BUY: 1, JUDGE_CONSIDER: 2, JUDGE_UNKNOWN: 3, JUDGE_SKIP: 4}
