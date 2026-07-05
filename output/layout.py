"""スプレッドシートの列構成・数式定義

設計書 6.2 の列を「判断に使う順」に並べ替えた改良レイアウト:
- 判定・利益・相場確認URLなど意思決定に使う列を左側に集約
- 原価の内訳（商品価格〜販売手数料）は右側にまとめ、Excelでは折りたたみ可能
- 「輸入経費」列を追加し、海外仕入れの輸入諸経費を実質仕入れ価格に含める
"""
from __future__ import annotations

from core.shipping import SIZE_LABELS

SHEET_CANDIDATES = "候補一覧"
SHEET_SETTINGS = "設定"
SHEET_PURCHASED = "仕入れ済み"
SHEET_LINKS = "検索リンク"

HEADERS = [
    "判定",              # A: ◎○△×/要目視（数式）
    "商品名",            # B
    "仕入れ元",          # C
    "状態",              # D
    "実質仕入れ価格",    # E: =O+P+R-Q（数式）
    "想定販売価格",      # F: 自動推定（目視確認後に手動上書き）
    "利益額",            # G: 数式
    "利益率",            # H: 数式
    "相場確認URL",       # I: メルカリ売り切れ検索
    "商品URL",           # J
    "サイズ区分",        # K: プルダウン
    "確定済み",          # L: 目視確認チェック
    "推定ステータス",    # M
    "注意フラグ",        # N
    "商品価格",          # O ┐
    "仕入れ送料",        # P │
    "ポイント還元",      # Q │ 内訳（折りたたみグループ）
    "輸入経費",          # R │
    "発送送料",          # S │ 数式
    "資材代",            # T │ 数式
    "販売手数料",        # U ┘ 数式
    "ROI",               # V: 数式
    "JAN/型番",          # W
    "取得日時",          # X
    "メモ",              # Y
]

# Excelで折りたたみ表示にする内訳列の範囲
DETAIL_GROUP = ("O", "U")

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
    """行 r（1始まり）の数式。想定販売価格(F)やサイズ(K)を変えると自動再計算される"""
    s = SHEET_SETTINGS
    imp = f"IF(ISNUMBER(FIND(\"輸入品\",$N{r})),{s}!$B$2,0)"
    return {
        # 実質仕入れ価格 = 商品価格 + 仕入れ送料 + 輸入経費 - ポイント還元
        "E": f"=IF($O{r}=\"\",\"\",$O{r}+$P{r}+$R{r}-$Q{r})",
        # 発送送料・資材代はサイズ区分から設定シートを参照
        "S": f"=IF($K{r}=\"\",\"\",VLOOKUP($K{r},{s}!$A$4:$C$9,2,FALSE))",
        "T": f"=IF($K{r}=\"\",\"\",VLOOKUP($K{r},{s}!$A$4:$C$9,3,FALSE))",
        # 販売手数料 = 想定販売価格 × 手数料率
        "U": f"=IF($F{r}=\"\",\"\",ROUND($F{r}*{s}!$B$1,0))",
        # 利益額 = 想定販売価格 - 実質仕入れ - 発送送料 - 資材代 - 手数料
        "G": f"=IF(OR($F{r}=\"\",$K{r}=\"\"),\"\",$F{r}-$E{r}-$S{r}-$T{r}-$U{r})",
        "H": f"=IF(OR($G{r}=\"\",$F{r}=0),\"\",$G{r}/$F{r})",
        "V": f"=IF(OR($G{r}=\"\",$E{r}=0),\"\",$G{r}/$E{r})",
        # 判定: 輸入品（注意フラグに「輸入品」を含む）は利益率基準に上乗せ（設計書4.6）
        "A": (
            f"=IF($F{r}=\"\",\"要目視\",IF($G{r}=\"\",\"要目視\","
            f"IF(AND($G{r}>={s}!$F$4,$H{r}>={s}!$G$4+{imp}),\"◎\","
            f"IF(AND($G{r}>={s}!$F$5,$H{r}>={s}!$G$5+{imp}),\"○\","
            f"IF(AND($G{r}>={s}!$F$6,$H{r}>={s}!$G$6+{imp}),\"△\",\"×\")))))"
        ),
    }
