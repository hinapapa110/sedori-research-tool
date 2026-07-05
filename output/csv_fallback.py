"""CSV退避出力（設計書 9章: Sheets書き込み失敗時のフォールバック）"""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from core.report import CandidateRow
from core.shipping import SIZE_LABELS
from output import layout

logger = logging.getLogger(__name__)


def write_csv(rows: list[CandidateRow], directory: str | Path = ".") -> Path:
    path = Path(directory) / f"candidates_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(layout.HEADERS)
        for row in rows:
            p = row.product
            est = row.estimate
            pr = row.profit
            writer.writerow([
                row.judgement,                                              # 判定
                p.title,                                                    # 商品名
                p.source,                                                   # 仕入れ元
                {"new": "新品", "used": "中古", "refurbished": "整備済"}.get(p.condition, "不明"),
                pr.effective_cost if pr else "",                            # 実質仕入れ
                est.estimated_price or "",                                  # 想定販売
                pr.profit if pr else "",                                    # 利益額
                f"{pr.margin:.1%}" if pr and pr.margin is not None else "",
                row.mercari_url,                                            # 相場確認URL
                p.url,                                                      # 商品URL
                SIZE_LABELS.get(row.size_key, ""),                          # サイズ区分
                "",                                                         # 確定済み
                est.status,                                                 # 推定ステータス
                " / ".join(row.flags),                                      # 注意フラグ
                p.price,
                p.shipping_cost,
                p.points,
                p.import_cost,
                pr.shipping_out if pr else "",
                pr.material if pr else "",
                pr.fee if pr else "",
                f"{pr.roi:.1%}" if pr and pr.roi is not None else "",       # ROI
                p.jan_code or "",
                p.fetched_at.strftime("%Y-%m-%d %H:%M"),
                f"換算: {p.currency_note}" if p.currency_note else "",
            ])
    logger.info("CSV出力: %s（%d件）", path, len(rows))
    return path
