"""損益計算のテスト（設計書 4.1 の計算式を検証）"""
from datetime import datetime

from core.profit import calc_profit, effective_cost
from models.product import Product


def make_product(**kwargs) -> Product:
    defaults = dict(
        source="rakuten", tier=1, product_id="x", title="テスト商品",
        url="https://example.com/item", price=3000, shipping_cost=0,
        condition="used", fetched_at=datetime(2026, 7, 3),
    )
    defaults.update(kwargs)
    return Product(**defaults)


class TestEffectiveCost:
    def test_basic(self):
        p = make_product(price=3000, shipping_cost=500, points=300)
        assert effective_cost(p) == 3200  # 3000 + 500 - 300

    def test_points_excluded(self):
        p = make_product(price=3000, shipping_cost=500, points=300)
        assert effective_cost(p, include_points=False) == 3500

    def test_import_cost_included(self):
        p = make_product(price=20000, import_cost=1500)
        assert effective_cost(p) == 21500

    def test_never_negative(self):
        p = make_product(price=100, points=500)
        assert effective_cost(p) == 0


class TestCalcProfit:
    def test_design_doc_formula(self):
        # 想定販売価格5000円 / 実質仕入れ3000円 / 60サイズ(750+80)
        result = calc_profit(5000, 3000, 0.10, 750, 80)
        assert result.fee == 500          # 5000 × 10%
        assert result.profit == 670       # 5000 - 3000 - 500 - 750 - 80
        assert abs(result.margin - 0.134) < 0.001
        assert abs(result.roi - 670 / 3000) < 0.001

    def test_negative_profit(self):
        result = calc_profit(1000, 2000, 0.10, 210, 30)
        assert result.profit == -1340
        assert result.margin < 0

    def test_zero_sell_price(self):
        result = calc_profit(0, 1000, 0.10, 210, 30)
        assert result.margin is None
