"""メルカリ配送サイズ・送料/資材代テーブル（設計書 4.3 / 4.4）"""
from __future__ import annotations

from dataclasses import dataclass


# 内部キー → 表示名（スプレッドシートのプルダウンにも使用）
SIZE_LABELS = {
    "nekopos": "ネコポス",
    "compact": "宅急便コンパクト",
    "size60": "宅急便60サイズ",
    "size80": "宅急便80サイズ",
    "size100": "宅急便100サイズ",
    "size120": "宅急便120サイズ以上",
}


@dataclass(frozen=True)
class ShippingEntry:
    key: str
    label: str
    shipping: int   # 発送送料（円）
    material: int   # 資材代（円）


class ShippingTable:
    """config.yaml の shipping / materials セクションから送料・資材代を引く"""

    def __init__(self, config: dict):
        ship = config.get("shipping", {})
        mat = config.get("materials", {})
        # 宅急便コンパクトは専用BOX代を送料側に合算（設計書 4.3）
        compact_total = int(ship.get("compact", 450)) + int(ship.get("compact_box", 70))
        self._entries: dict[str, ShippingEntry] = {
            "nekopos": ShippingEntry("nekopos", SIZE_LABELS["nekopos"],
                                     int(ship.get("nekopos", 210)), int(mat.get("nekopos", 30))),
            "compact": ShippingEntry("compact", SIZE_LABELS["compact"],
                                     compact_total, int(mat.get("compact", 20))),
            "size60": ShippingEntry("size60", SIZE_LABELS["size60"],
                                    int(ship.get("size60", 750)), int(mat.get("size60_80", 80))),
            "size80": ShippingEntry("size80", SIZE_LABELS["size80"],
                                    int(ship.get("size80", 850)), int(mat.get("size60_80", 80))),
            "size100": ShippingEntry("size100", SIZE_LABELS["size100"],
                                     int(ship.get("size100", 1050)), int(mat.get("size100_over", 150))),
            "size120": ShippingEntry("size120", SIZE_LABELS["size120"],
                                     int(ship.get("size120", 1200)), int(mat.get("size100_over", 150))),
        }

    def get(self, size_key: str) -> ShippingEntry:
        if size_key not in self._entries:
            raise KeyError(f"未知のサイズ区分: {size_key}（有効: {list(self._entries)}）")
        return self._entries[size_key]

    def entries(self) -> list[ShippingEntry]:
        return list(self._entries.values())

    def labels(self) -> list[str]:
        return [e.label for e in self._entries.values()]
