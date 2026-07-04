"""Excel（.xlsx）出力（設計書 6章）

- 候補一覧: 追記型・URL基準で重複スキップ・数式/リンク/プルダウン付き
- 設定: 送料・資材代・判定基準テーブル（数式が参照）
- 仕入れ済み: 在庫管理の入口（空シート）
- 検索リンク: Tier3サイトの検索URL
"""
from __future__ import annotations

import logging
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from core.report import CandidateRow
from core.shipping import SIZE_LABELS, ShippingTable
from output import layout

logger = logging.getLogger(__name__)

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
LINK_FONT = Font(color="0563C1", underline="single")

JUDGE_FILLS = {
    "◎": PatternFill("solid", fgColor="C6EFCE"),
    "○": PatternFill("solid", fgColor="E2EFDA"),
    "△": PatternFill("solid", fgColor="FFF2CC"),
    "×": PatternFill("solid", fgColor="D9D9D9"),
}


class ExcelWriter:
    def __init__(self, config: dict, path: str | Path):
        self.config = config
        self.path = Path(path)

    # ------------------------------------------------------------------
    def write(self, rows: list[CandidateRow], tier3_links: list[dict]) -> Path:
        if self.path.exists():
            wb = load_workbook(self.path)
        else:
            wb = self._create_workbook()

        ws = wb[layout.SHEET_CANDIDATES]
        existing_urls = self._existing_urls(ws)

        appended = 0
        for row in rows:
            if row.product.url in existing_urls:
                continue
            self._append_row(ws, row)
            existing_urls.add(row.product.url)
            appended += 1

        self._apply_validations(ws)
        self._apply_conditional_formatting(ws)

        if tier3_links:
            self._append_links(wb[layout.SHEET_LINKS], tier3_links)

        wb.save(self.path)
        logger.info("Excel出力: %s（新規 %d件 / 重複スキップ %d件）",
                    self.path, appended, len(rows) - appended)
        return self.path

    # ------------------------------------------------------------------
    def _create_workbook(self) -> Workbook:
        wb = Workbook()
        ws = wb.active
        ws.title = layout.SHEET_CANDIDATES
        self._write_header(ws, layout.HEADERS)
        ws.freeze_panes = "A2"

        widths = [17, 11, 45, 12, 15, 8, 10, 10, 10, 10, 12, 12, 11, 12, 8, 16,
                  9, 8, 10, 10, 8, 8, 8, 22, 20]
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

        settings = wb.create_sheet(layout.SHEET_SETTINGS)
        table = ShippingTable(self.config)
        for row in layout.settings_rows(self.config, table.entries()):
            settings.append(row)
        settings["B1"].number_format = "0%"
        settings["B2"].number_format = "0%"
        for r in (4, 5, 6):
            settings.cell(row=r, column=7).number_format = "0%"
        for col, w in zip("ABCDEFG", [24, 10, 10, 4, 14, 10, 10]):
            settings.column_dimensions[col].width = w

        purchased = wb.create_sheet(layout.SHEET_PURCHASED)
        self._write_header(purchased, layout.HEADERS)

        links = wb.create_sheet(layout.SHEET_LINKS)
        self._write_header(links, layout.LINKS_HEADERS)
        for col, w in zip("ABCD", [17, 30, 16, 60]):
            links.column_dimensions[col].width = w

        return wb

    @staticmethod
    def _write_header(ws, headers: list[str]) -> None:
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")

    @staticmethod
    def _existing_urls(ws) -> set[str]:
        urls: set[str] = set()
        for row in ws.iter_rows(min_row=2, min_col=4, max_col=4):
            cell = row[0]
            if cell.hyperlink and cell.hyperlink.target:
                urls.add(cell.hyperlink.target)
            elif isinstance(cell.value, str) and cell.value.startswith("http"):
                urls.add(cell.value)
        return urls

    # ------------------------------------------------------------------
    def _append_row(self, ws, row: CandidateRow) -> None:
        p = row.product
        r = ws.max_row + 1
        est = row.estimate

        values = {
            "A": p.fetched_at.strftime("%Y-%m-%d %H:%M"),
            "B": p.source,
            "C": p.title,
            "D": p.url,
            "E": p.jan_code or "",
            "F": {"new": "新品", "used": "中古", "refurbished": "整備済"}.get(p.condition, "不明"),
            "G": p.price,
            "H": p.shipping_cost,
            "I": p.points,
            "J": p.import_cost,
            "L": est.estimated_price if est.estimated_price else "",
            "M": est.status + (f"({est.sample_count}件)" if est.sample_count else ""),
            "O": "",
            "P": SIZE_LABELS.get(row.size_key, ""),
            "X": " / ".join(row.flags),
            "Y": f"換算: {p.currency_note}" if p.currency_note else "",
        }
        for col, value in values.items():
            ws[f"{col}{r}"] = value
        for col, formula in layout.row_formulas(r).items():
            ws[f"{col}{r}"] = formula

        # ハイパーリンク（D: 商品URL / N: メルカリ相場確認URL）
        d = ws[f"D{r}"]
        d.value = "商品を開く"
        d.hyperlink = p.url
        d.font = LINK_FONT
        if row.mercari_url:
            n = ws[f"N{r}"]
            n.value = "相場を見る"
            n.hyperlink = row.mercari_url
            n.font = LINK_FONT

        for col in "GHIJKLQRST":
            ws[f"{col}{r}"].number_format = "#,##0"
        for col in "UV":
            ws[f"{col}{r}"].number_format = "0.0%"

    def _apply_validations(self, ws) -> None:
        # openpyxlはロード時に既存validationを保持するが、範囲を張り直してシンプルに保つ
        ws.data_validations.dataValidation = []
        size_dv = DataValidation(
            type="list",
            formula1='"' + ",".join(layout.SIZE_DROPDOWN) + '"',
            allow_blank=True,
            showDropDown=False,
        )
        size_dv.add("P2:P10000")
        ws.add_data_validation(size_dv)

        confirm_dv = DataValidation(type="list", formula1='"✔"', allow_blank=True,
                                    showDropDown=False)
        confirm_dv.add("O2:O10000")
        ws.add_data_validation(confirm_dv)

    def _apply_conditional_formatting(self, ws) -> None:
        ws.conditional_formatting = type(ws.conditional_formatting)()
        for mark, fill in JUDGE_FILLS.items():
            ws.conditional_formatting.add(
                "W2:W10000",
                CellIsRule(operator="equal", formula=[f'"{mark}"'], fill=fill),
            )

    # ------------------------------------------------------------------
    def _append_links(self, ws, tier3_links: list[dict]) -> None:
        existing = {
            (row[1].value, row[2].value)
            for row in ws.iter_rows(min_row=2, max_col=4)
        }
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        for link in tier3_links:
            if (link["query"], link["site"]) in existing:
                continue
            r = ws.max_row + 1
            ws[f"A{r}"] = now
            ws[f"B{r}"] = link["query"]
            ws[f"C{r}"] = link["site"]
            cell = ws[f"D{r}"]
            cell.value = link["url"]
            cell.hyperlink = link["url"]
            cell.font = LINK_FONT
