"""海外仕入れ（輸入）コストの概算（設計書 4.6）

輸入諸経費（概算） = 関税 + 輸入消費税 + 通関手数料

- 個人輸入の課税価格は「商品代金 × 評価率（デフォルト60%）」で概算
- 課税価格が免税基準（デフォルト1万円）以下なら原則免税として 0 円
- あくまで概算。転売目的の輸入は個人使用の免税評価が適用されない場合が
  あるため、本格化する際は税関・税理士に確認すること（設計書 11-9）
"""
from __future__ import annotations


def estimate_import_cost(goods_price_jpy: int, config: dict) -> int:
    """商品代金（円換算済み）から輸入諸経費を概算する。

    国際送料は課税価格の簡易評価（60%ルール）に含めない前提の概算。
    """
    imp = config.get("import", {})
    valuation = float(imp.get("customs_valuation", 0.60))
    threshold = int(imp.get("duty_free_threshold", 10000))
    duty_rate = float(imp.get("simple_duty_rate", 0.05))
    tax_rate = float(imp.get("consumption_tax", 0.10))
    handling = int(imp.get("customs_handling_fee", 200))

    taxable = round(goods_price_jpy * valuation)
    if taxable <= threshold:
        return 0  # 免税（関税・消費税とも課されない前提の概算）

    duty = taxable * duty_rate
    consumption_tax = (taxable + duty) * tax_rate
    return int(round(duty + consumption_tax + handling))
