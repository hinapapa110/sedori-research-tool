"""送料・資材代テーブルのテスト（設計書 4.3 / 4.4）"""
import pytest

from core.shipping import ShippingTable


class TestShippingTable:
    def test_values_from_config(self, config):
        table = ShippingTable(config)
        assert table.get("nekopos").shipping == 210
        assert table.get("nekopos").material == 30
        assert table.get("size60").shipping == 750
        assert table.get("size60").material == 80
        assert table.get("size100").material == 150

    def test_compact_includes_box(self, config):
        # 宅急便コンパクトは専用BOX代70円を送料に合算
        table = ShippingTable(config)
        assert table.get("compact").shipping == 520

    def test_unknown_size_raises(self, config):
        with pytest.raises(KeyError):
            ShippingTable(config).get("size999")

    def test_defaults_without_config(self):
        table = ShippingTable({})
        assert table.get("nekopos").shipping == 210
        assert len(table.entries()) == 6
