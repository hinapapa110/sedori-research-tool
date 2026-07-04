"""検索URL生成のテスト（設計書 3.4-② / Tier3）"""
from core.url_builder import build_tier3_links, mercari_soldout_url, site_search_url


class TestMercariUrl:
    def test_soldout_url(self, config):
        url = mercari_soldout_url("ワイヤレスイヤホン", config)
        assert url.startswith("https://jp.mercari.com/search?")
        assert "status=sold_out" in url
        assert "%E3%83%AF%E3%82%A4%E3%83%A4%E3%83%AC%E3%82%B9" in url  # URLエンコード済み

    def test_default_template_without_config(self):
        url = mercari_soldout_url("test")
        assert url == "https://jp.mercari.com/search?keyword=test&status=sold_out"


class TestTier3Links:
    def test_build_links(self, config):
        links = build_tier3_links("ゲームボーイ", config["sites"]["tier3"])
        assert len(links) == 4
        sites = {l["site"] for l in links}
        assert sites == {"ヤフオク", "ラクマ", "Temu", "Qoo10"}
        for l in links:
            assert l["url"].startswith("https://")

    def test_unknown_site_skipped(self):
        links = build_tier3_links("x", ["unknown_site", "rakuma"])
        assert len(links) == 1

    def test_query_encoded(self):
        url = site_search_url("yahoo_auction", "ポケモン カード")
        assert " " not in url
