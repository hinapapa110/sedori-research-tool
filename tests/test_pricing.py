"""相場推定のテスト（設計書 3.4 / 4.5 + 型番・類似フォールバック）"""
from core.pricing import (
    BASIS_JAN,
    BASIS_MODEL,
    BASIS_SIMILAR,
    STATUS_NONE,
    STATUS_OK,
    STATUS_REF,
    PriceEstimator,
    extract_model_tokens,
    normalize_title,
    title_similarity,
)
from tests.test_profit import make_product

JAN = "4901234567890"


def ref(price: int, i: int, source="yahoo", condition="used", jan=JAN, title="テスト商品"):
    return make_product(
        source=source, price=price, jan_code=jan, condition=condition,
        url=f"https://example.com/ref{i}", title=title,
    )


def jan_only_config(config):
    """フォールバック無効（JAN一致のみ）の設定"""
    config["pricing"]["fallback_model_match"] = False
    config["pricing"]["title_similarity_threshold"] = 0
    return config


class TestJanMatch:
    def test_median_times_factor(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1), ref(5000, 2), ref(6000, 3)]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.reference_median == 5000
        assert est.estimated_price == 4250  # 5000 × 0.85
        assert est.status == STATUS_OK
        assert est.basis == BASIS_JAN
        assert est.sample_count == 3
        assert "JAN一致3件" in est.label

    def test_few_samples_is_reference_only(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        est = PriceEstimator(config).estimate(candidate, [candidate, ref(4000, 1)])
        assert est.status == STATUS_REF

    def test_no_jan_no_fallback_means_no_estimate(self, config):
        candidate = make_product(jan_code=None, title="別の商品ZZZ")
        est = PriceEstimator(jan_only_config(config)).estimate(
            candidate, [candidate, ref(4000, 1)])
        assert est.status == STATUS_NONE
        assert est.estimated_price is None

    def test_excludes_self(self, config):
        candidate = make_product(jan_code=JAN, source="rakuten",
                                 url="https://example.com/self")
        est = PriceEstimator(config).estimate(candidate, [candidate])
        assert est.status == STATUS_NONE

    def test_condition_match_preferred(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(4000, 1, condition="used"), ref(9000, 2, condition="new")]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.reference_median == 4000
        assert est.sample_count == 1

    def test_non_reference_site_excluded(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya",
                                 title="ユニーク商品XYZ999Q")
        refs = [ref(4000, 1, source="ebay")]  # eBayは参照サイトではない
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.status == STATUS_NONE


class TestModelMatchFallback:
    def test_model_number_match(self, config):
        # JANなしでも型番（WH-1000XM4）一致で推定できる
        candidate = make_product(jan_code=None, condition="used", source="rakuten",
                                 title="【中古】SONY ワイヤレスヘッドホン WH-1000XM4 ブラック")
        refs = [
            ref(20000, 1, jan=None, title="ソニー WH-1000XM4 ヘッドホン 中古美品"),
            ref(22000, 2, jan=None, title="SONY WH-1000XM4 プレミアムノイキャン 中古"),
            ref(24000, 3, jan=None, title="wh-1000xm4 SONY ヘッドフォン（中古）"),
        ]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.basis == BASIS_MODEL
        assert est.reference_median == 22000
        assert est.status == STATUS_OK  # 3件以上なら推定OK

    def test_jan_takes_priority_over_model(self, config):
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya",
                                 title="SONY WH-1000XM4")
        refs = [
            ref(5000, 1, jan=JAN, title="無関係な商品名"),
            ref(30000, 2, jan=None, title="SONY WH-1000XM4 中古"),
        ]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.basis == BASIS_JAN
        assert est.reference_median == 5000


class TestSimilarityFallback:
    def test_similar_title_is_reference_only(self, config):
        # 型番もJANもないが、タイトルがほぼ同じ → 参考値
        candidate = make_product(jan_code=None, condition="used", source="rakuten",
                                 title="【中古】ポケモンカードゲーム MEGA 拡張パック アビスアイ 5パック")
        refs = [
            ref(1400, 1, jan=None,
                title="ポケモンカードゲーム MEGA 拡張パック アビスアイ 5パック ばら売り"),
            ref(1500, 2, jan=None,
                title="【送料無料】ポケモンカードゲーム MEGA 拡張パック アビスアイ 5パック"),
        ]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.basis == BASIS_SIMILAR
        assert est.status == STATUS_REF  # 類似一致は件数によらず参考値
        assert est.estimated_price is not None

    def test_dissimilar_title_no_estimate(self, config):
        candidate = make_product(jan_code=None, title="レトロゲーム機 まとめ売り ジャンク")
        refs = [ref(4000, 1, jan=None, title="ワイヤレスイヤホン Bluetooth 5.3 防水")]
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.status == STATUS_NONE

    def test_outlier_prices_dropped(self, config):
        # ケース等の付属品（極端に安い）が混ざっても除外される
        candidate = make_product(jan_code=JAN, condition="used", source="surugaya")
        refs = [ref(5000, 1), ref(5200, 2), ref(300, 3)]  # 300円は外れ値
        est = PriceEstimator(config).estimate(candidate, [candidate] + refs)
        assert est.sample_count == 2
        assert est.reference_median == 5100


class TestHelpers:
    def test_extract_model_tokens(self):
        assert "WH-1000XM4" in extract_model_tokens("SONY WH-1000XM4 ブラック")
        assert "BTE-A1000" in extract_model_tokens("ALPEX イヤホン BTE-A1000/エメラルド")
        assert extract_model_tokens("ポケモンカード 5パック") == set()

    def test_normalize_removes_noise(self):
        a = normalize_title("【中古】【送料無料】SONY ヘッドホン 期間限定セール")
        assert "中古" not in a and "送料無料" not in a and "sony" in a

    def test_similarity_range(self):
        a = normalize_title("ポケモンカードゲーム MEGA 拡張パック アビスアイ")
        b = normalize_title("【新品】ポケモンカードゲーム MEGA 拡張パック アビスアイ BOX")
        assert title_similarity(a, b) > 0.6
        c = normalize_title("ワイヤレスイヤホン Bluetooth")
        assert title_similarity(a, c) < 0.2
