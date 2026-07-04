"""仕入れ判定のテスト（設計書 5章）"""
from core.judge import JUDGE_BUY, JUDGE_CONSIDER, JUDGE_SKIP, JUDGE_STRONG, JUDGE_UNKNOWN, flags, judge
from core.profit import calc_profit
from tests.test_profit import make_product


def result_with(profit: int, sell: int):
    """指定の利益額・販売価格になる ProfitResult を作る"""
    cost = sell - profit - round(sell * 0.10)
    return calc_profit(sell, cost, 0.10, 0, 0)


class TestJudge:
    def test_strong_buy(self, config):
        # 利益2500円・利益率25%以上
        r = result_with(2500, 10000)
        assert judge(r, config) == JUDGE_STRONG

    def test_buy(self, config):
        r = result_with(900, 5000)  # 18%
        assert judge(r, config) == JUDGE_BUY

    def test_consider(self, config):
        r = result_with(550, 5000)  # 11%
        assert judge(r, config) == JUDGE_CONSIDER

    def test_skip_low_profit(self, config):
        r = result_with(300, 5000)
        assert judge(r, config) == JUDGE_SKIP

    def test_skip_negative(self, config):
        r = result_with(-500, 5000)
        assert judge(r, config) == JUDGE_SKIP

    def test_unknown_when_no_estimate(self, config):
        assert judge(None, config) == JUDGE_UNKNOWN

    def test_import_risk_premium(self, config):
        # 利益率16%: 国内なら○だが、輸入品は+5%上乗せで20%必要 → △
        r = result_with(800, 5000)
        assert judge(r, config, is_import=False) == JUDGE_BUY
        assert judge(r, config, is_import=True) == JUDGE_CONSIDER

    def test_profit_and_margin_both_required(self, config):
        # 利益額は◎基準でも利益率が低ければ格下げ
        r = result_with(1600, 20000)  # 8%
        assert judge(r, config) == JUDGE_SKIP


class TestFlags:
    def test_high_price_flag(self, config):
        p = make_product(price=15000)
        r = calc_profit(20000, 15000, 0.10, 750, 80)
        assert "高額仕入れ" in flags(p, r, config)

    def test_import_flags(self, config):
        p = make_product(is_import=True, currency_note="USD 20.00 @155.0")
        r = calc_profit(5000, 3000, 0.10, 750, 80)
        f = flags(p, r, config)
        assert "輸入品注意" in f
        assert "為替注意" in f

    def test_thin_profit_flag(self, config):
        # 利益率高いが利益額500円以下
        r = calc_profit(2000, 1000, 0.10, 210, 30)  # profit=560 → 対象外
        p = make_product()
        assert "薄利多売" not in flags(p, r, config)
        r2 = calc_profit(1500, 800, 0.10, 210, 30)  # profit=340, margin=22.7%
        assert "薄利多売" in flags(p, r2, config)

    def test_large_size_flag(self, config):
        p = make_product()
        r = calc_profit(5000, 1000, 0.10, 1050, 150)
        assert "大型注意" in flags(p, r, config, size_key="size100")

    def test_needs_check_flag(self, config):
        p = make_product()
        assert "要目視" in flags(p, None, config, estimate_status="推定不能")
