"""輸入コスト概算のテスト（設計書 4.6）"""
from core.import_cost import estimate_import_cost


class TestImportCost:
    def test_duty_free_below_threshold(self, config):
        # 商品代金16,666円 → 課税価格9,999円 ≤ 1万円 → 免税
        assert estimate_import_cost(16000, config) == 0

    def test_taxed_above_threshold(self, config):
        # 商品代金20,000円 → 課税価格12,000円
        # 関税 12000×5%=600 / 消費税 (12000+600)×10%=1260 / 手数料200 → 2060
        assert estimate_import_cost(20000, config) == 2060

    def test_boundary(self, config):
        # 課税価格ちょうど1万円は免税
        assert estimate_import_cost(16667, config) == 0
        assert estimate_import_cost(16668, config) > 0
