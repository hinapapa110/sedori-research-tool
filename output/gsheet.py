"""Google Sheets出力（設計書 6章）

- gspread + サービスアカウント認証（GOOGLE_SHEETS_CREDENTIALS）
- 数式・ハイパーリンクは USER_ENTERED で書き込み、手動上書きで自動再計算
- 書き込み失敗時は呼び出し側（main.py）がCSVへ退避（設計書 9章）
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from core.report import CandidateRow
from core.shipping import SIZE_LABELS, ShippingTable
from output import layout

logger = logging.getLogger(__name__)


class GoogleSheetsWriter:
    def __init__(self, config: dict):
        self.config = config
        self.spreadsheet_name = config.get("output", {}).get(
            "gsheet_name", "仕入れ候補発掘ツール"
        )

    def write(self, rows: list[CandidateRow], tier3_links: list[dict]) -> str:
        import gspread  # 遅延import: Excel運用のみの環境でも動くように

        creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS", "credentials.json")
        gc = gspread.service_account(filename=creds_path)

        try:
            sh = gc.open(self.spreadsheet_name)
        except gspread.SpreadsheetNotFound:
            sh = gc.create(self.spreadsheet_name)
            logger.info("スプレッドシート新規作成: %s", self.spreadsheet_name)

        ws = self._ensure_sheet(sh, layout.SHEET_CANDIDATES, layout.HEADERS)
        self._ensure_settings(sh)
        self._ensure_sheet(sh, layout.SHEET_PURCHASED, layout.HEADERS)
        links_ws = self._ensure_sheet(sh, layout.SHEET_LINKS, layout.LINKS_HEADERS)

        existing_urls = set(ws.col_values(10)[1:])  # J列（商品URLはHYPERLINK式のため式文字列ごと比較）
        new_values: list[list] = []
        start_row = len(ws.get_all_values()) + 1
        r = start_row
        appended = 0
        for row in rows:
            url_formula = f'=HYPERLINK("{row.product.url}","商品を開く")'
            if row.product.url in existing_urls or url_formula in existing_urls:
                continue
            new_values.append(self._row_values(row, r))
            existing_urls.add(url_formula)
            r += 1
            appended += 1

        if new_values:
            ws.update(
                f"A{start_row}:Y{start_row + len(new_values) - 1}",
                new_values,
                value_input_option="USER_ENTERED",
            )

        if tier3_links:
            self._append_links(links_ws, tier3_links)

        logger.info("Google Sheets出力: %s（新規 %d件 / 重複スキップ %d件）",
                    sh.url, appended, len(rows) - appended)
        return sh.url

    # ------------------------------------------------------------------
    def _row_values(self, row: CandidateRow, r: int) -> list:
        p = row.product
        est = row.estimate
        formulas = layout.row_formulas(r)
        mercari = (
            f'=HYPERLINK("{row.mercari_url}","相場を見る")' if row.mercari_url else ""
        )
        return [
            formulas["A"],                                                  # A 判定
            p.title,                                                        # B
            p.source,                                                       # C
            {"new": "新品", "used": "中古", "refurbished": "整備済"}.get(p.condition, "不明"),  # D
            formulas["E"],                                                  # E 実質仕入れ
            est.estimated_price if est.estimated_price else "",             # F 想定販売
            formulas["G"], formulas["H"],                                   # G 利益額 / H 利益率
            mercari,                                                        # I 相場確認
            f'=HYPERLINK("{p.url}","商品を開く")',                          # J 商品URL
            SIZE_LABELS.get(row.size_key, ""),                              # K サイズ区分
            "",                                                             # L 確定済み
            est.label,                                                      # M

            " / ".join(row.flags),                                          # N 注意フラグ
            p.price,                                                        # O
            p.shipping_cost,                                                # P
            p.points,                                                       # Q
            p.import_cost,                                                  # R
            formulas["S"], formulas["T"], formulas["U"],                    # S-U
            formulas["V"],                                                  # V ROI
            p.jan_code or "",                                               # W
            p.fetched_at.strftime("%Y-%m-%d %H:%M"),                        # X
            f"換算: {p.currency_note}" if p.currency_note else "",          # Y
        ]

    @staticmethod
    def _ensure_sheet(sh, title: str, headers: list[str]):
        try:
            ws = sh.worksheet(title)
        except Exception:  # noqa: BLE001 - WorksheetNotFound
            ws = sh.add_worksheet(title=title, rows=1000, cols=len(headers) + 2)
            ws.update("A1", [headers])
        return ws

    def _ensure_settings(self, sh) -> None:
        try:
            sh.worksheet(layout.SHEET_SETTINGS)
            return  # 既存の設定シートは上書きしない（ユーザー調整を尊重）
        except Exception:  # noqa: BLE001
            ws = sh.add_worksheet(title=layout.SHEET_SETTINGS, rows=50, cols=10)
            table = ShippingTable(self.config)
            ws.update("A1", layout.settings_rows(self.config, table.entries()),
                      value_input_option="USER_ENTERED")

    @staticmethod
    def _append_links(ws, tier3_links: list[dict]) -> None:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        values = [
            [now, link["query"], link["site"],
             f'=HYPERLINK("{link["url"]}","{link["site"]}で検索")']
            for link in tier3_links
        ]
        ws.append_rows(values, value_input_option="USER_ENTERED")
