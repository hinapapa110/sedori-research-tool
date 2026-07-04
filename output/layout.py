"""スプレッドシートの列構成・数式定義（設計書 6.2 を拡張）

設計書 v1.3 からの改善点: 「輸入経費」列（J）を追加し、海外仕入れの
輸入諸経費を実質仕入れ価格の数式に含めた。以降の列は1つずつ後ろへずれる。
"""
from __future__ import annotations

from core.shipping import SIZE_LABELS

SHEET_CANDIDATES = "候補一覧"
SHEET_SETTINGS = "設定"
SHEET_PURCHASED = "仕入れ済み"
SHEET_LINKS = "検索リンク"

HEADERS = [
    "取得日時",          # A
    "仕入れ元",          # B
    "商品名",            # C
    "商品URL",           # D
    "JAN/型番",          # E
    "状態",              # F
    "商品価格",          # G
    "仕入れ送料",        # H
    "ポイント還元",      # I
    "輸入経費",          # J
    "実質仕入れ価格",    # K
    "想定販売価格",      # L
    "推定ステータス",    # M
    "相場確認URL",       # N
    "確定済み",          # O
    "サイズ区分",        # P
    "発送送料",          # Q
    "資材代",            # R
    "販売手数料",        # S
    "利益額",            # T
    "利益率",            # U
    "ROI",               # V
    "判定",              # W
    "注意フラグ",        # X
    "メモ",              # Y
]

LINKS_HEADERS = ["取得日時", "検索語", "サイト", "検索URL"]

SIZE_DROPDOWN = list(SIZE_LABELS.values())
CONFIRM_DROPDOWN = ["✔"]

# 設定シートのセル配置（数式が参照する）
#   B1: 販売手数料率 / B2: 輸入リスク上乗せ（利益率に加算）
#   A4:C9: サイズ区分・送料・資材代テーブル
#   F4:G6: 判定基準（利益額・利益率）


def settings_rows(config: dict, shipping_entries) -> list[list]:
    jc = config.get("judge", {})
    rows = [
        ["販売手数料率", float(config.get("mercari", {}).get("fee_rate", 0.10)), "",
         "", "", "", ""],
        ["輸入リスク上乗せ(利益率)", float(config.get("import", {}).get("risk_margin_add", 0.05)),
         "", "", "", "", ""],
        ["サイズ区分", "送料", "資材代", "", "判定", "利益額≥", "利益率≥"],
    ]
    judge_rows = [
        ["◎ 強い買い", int(jc.get("strong_buy", {}).get("profit", 1500)),
         float(jc.get("strong_buy", {}).get("margin", 0.25))],
        ["○ 買い", int(jc.get("buy", {}).get("profit", 800)),
         float(jc.get("buy", {}).get("margin", 0.15))],
        ["△ 要検討", int(jc.get("consider", {}).get("profit", 500)),
         float(jc.get("consider", {}).get("margin", 0.10))],
    ]
    for i, entry in enumerate(shipping_entries):
        judge = judge_rows[i] if i < len(judge_rows) else ["", "", ""]
        rows.append([entry.label, entry.shipping, entry.material, "", *judge])
    return rows


def row_formulas(r: int) -> dict[str, str]:
    """行 r（1始まり）の数式。手動で想定販売価格(L)やサイズ(P)を変えると自動再計算される"""
    s = SHEET_SETTINGS
    return {
        # 実質仕入れ価格 = 商品価格 + 仕入れ送料 + 輸入経費 - ポイント還元
        "K": f"=IF($G{r}=\"\",\"\",$G{r}+$H{r}+$J{r}-$I{r})",
        # 発送送料・資材代はサイズ区分から設定シートを参照
        "Q": f"=IF($P{r}=\"\",\"\",VLOOKUP($P{r},{s}!$A$4:$C$9,2,FALSE))",
        "R": f"=IF($P{r}=\"\",\"\",VLOOKUP($P{r},{s}!$A$4:$C$9,3,FALSE))",
        # 販売手数料 = 想定販売価格 × 手数料率
        "S": f"=IF($L{r}=\"\",\"\",ROUND($L{r}*{s}!$B$1,0))",
        # 利益額 = 想定販売価格 - 実質仕入れ - 発送送料 - 資材代 - 手数料
        "T": f"=IF(OR($L{r}=\"\",$P{r}=\"\"),\"\",$L{r}-$K{r}-$Q{r}-$R{r}-$S{r})",
        "U": f"=IF(OR($T{r}=\"\",$L{r}=0),\"\",$T{r}/$L{r})",
        "V": f"=IF(OR($T{r}=\"\",$K{r}=0),\"\",$T{r}/$K{r})",
        # 判定: 輸入品（注意フラグに「輸入品」を含む）は利益率基準に上乗せ（設計書4.6）
        "W": (
            f"=IF($L{r}=\"\",\"要目視\",IF($T{r}=\"\",\"要目視\","
            f"IF(AND($T{r}>={s}!$F$4,$U{r}>={s}!$G$4+IF(ISNUMBER(FIND(\"輸入品\",$X{r})),{s}!$B$2,0)),\"◎\","
            f"IF(AND($T{r}>={s}!$F$5,$U{r}>={s}!$G$5+IF(ISNUMBER(FIND(\"輸入品\",$X{r})),{s}!$B$2,0)),\"○\","
            f"IF(AND($T{r}>={s}!$F$6,$U{r}>={s}!$G$6+IF(ISNUMBER(FIND(\"輸入品\",$X{r})),{s}!$B$2,0)),\"△\",\"×\")))))"
        ),
    }
