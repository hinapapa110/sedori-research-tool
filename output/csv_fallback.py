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
                p.fetched_at.strftime("%Y-%m-%d %H:%M"),
                p.source,
                p.title,
                p.url,
                p.jan_code or "",
                {"new": "新品", "used": "中古", "refurbished": "整備済"}.get(p.condition, "不明"),
                p.price,
                p.shipping_cost,
                p.points,
                p.import_cost,
                pr.effective_cost if pr else "",
                est.estimated_price or "",
                est.status,
                row.mercari_url,
                "",
                SIZE_LABELS.get(row.size_key, ""),
                pr.shipping_out if pr else "",
                pr.material if pr else "",
                pr.fee if pr else "",
                pr.profit if pr else "",
                f"{pr.margin:.1%}" if pr and pr.margin is not None else "",
                f"{pr.roi:.1%}" if pr and pr.roi is not None else "",
                row.judgement,
                " / ".join(row.flags),
                f"換算: {p.currency_note}" if p.currency_note else "",
            ])
    logger.info("CSV出力: %s（%d件）", path, len(rows))
    return path
