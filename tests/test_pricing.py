"""相場推定のテスト（設計書 3.4 / 4.5）"""
from core.pricing import STATUS_NONE, STATUS_OK, STATUS_REF, PriceEstimator
from tests.test_profit import make_product

JAN = "4901234567890"


def ref(price: int, i: int, source="yahoo", condition="used"):
    return make_product(
        source=source, price=price, jan_code=JAN, condition=condition,
        url=f"https://example.com/ref{i}",
    )


class TestPriceEstimator:
    def test_median_times_factor(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1), ref(5000, 2), ref(6000, 3)]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.reference_median == 5000
        assert est.estimated_price == 4250  # 5000 × 0.85
        assert est.status == STATUS_OK
        assert est.sample_count == 3

    def test_few_samples_is_reference_only(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1)]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.status == STATUS_REF

    def test_no_jan_means_no_estimate(self, config):
        candidate = make_product(jan_code=None)
        est = PriceEstimator(config).estimate(candidate, [candidate, ref(4000, 1)])
        assert est.status == STATUS_NONE
        assert est.estimated_price is None

    def test_excludes_self(self, config):
        candidate = make_product(jan_code=JAN, source="rakuten",
                                 url="https://example.com/self")
        est = PriceEstimator(config).estimate(candidate, [candidate])
        assert est.status == STATUS_NONE

    def test_condition_match_preferred(self, config):
        # 中古候補には中古サンプルのみを使う（新品価格が混ざらない）
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1, condition="used"), ref(9000, 2, condition="new")]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.reference_median == 4000
        assert est.sample_count == 1

    def test_non_reference_site_excluded(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1, source="ebay")]  # eBayは参照サイトではない
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.status == STATUS_NONE
