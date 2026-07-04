#!/usr/bin/env python3
"""仕入れ候補発掘ツール — エントリーポイント（CLI）

使用例:
    python main.py search --keyword "ワイヤレスイヤホン" --max 20
    python main.py search --jan 4901234567890
    python main.py search --keyword "○○" --sites rakuten,yahoo
    python main.py search --keyword "○○" --condition used --output gsheet
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml
from dotenv import load_dotenv

from connectors.base import BaseConnector, ConnectorError
from core.exchange import ExchangeRates
from core.report import build_rows, dedupe_products, filter_rows
from core.url_builder import build_tier3_links
from models.product import Product, SearchQuery

logger = logging.getLogger("sedori")

BASE_DIR = Path(__file__).resolve().parent


# ----------------------------------------------------------------------
def load_config(path: str | None = None) -> dict:
    config_path = Path(path) if path else BASE_DIR / "config.yaml"
    if not config_path.exists():
        logger.warning("config.yaml が見つかりません（デフォルト値で動作）: %s", config_path)
        return {}
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_connectors(config: dict, sites_filter: list[str] | None) -> list[BaseConnector]:
    """設定と --sites 指定から有効なコネクタ一覧を組み立てる"""
    from connectors.aliexpress import AliExpressConnector
    from connectors.amazon import AmazonConnector
    from connectors.bookoff import BookoffConnector
    from connectors.ebay import EbayConnector
    from connectors.hardoff import HardoffConnector
    from connectors.rakuten import RakutenConnector
    from connectors.surugaya import SurugayaConnector
    from connectors.yahoo import YahooConnector

    exchange = ExchangeRates(config)
    registry: dict[str, BaseConnector] = {
        "rakuten": RakutenConnector(config),
        "yahoo": YahooConnector(config),
        "amazon": AmazonConnector(config),
        "ebay": EbayConnector(config, exchange),
        "aliexpress": AliExpressConnector(config, exchange),
        "surugaya": SurugayaConnector(config),
        "bookoff": BookoffConnector(config),
        "hardoff": HardoffConnector(config),
    }

    sites_cfg = config.get("sites", {})
    enabled = list(sites_cfg.get("tier1", ["rakuten", "yahoo"]))
    if sites_cfg.get("tier2_scraping_enabled", False):
        enabled += list(sites_cfg.get("tier2", []))

    if sites_filter:
        enabled = [s for s in sites_filter if s in registry]
        unknown = [s for s in sites_filter if s not in registry]
        for s in unknown:
            logger.warning("未知のサイト指定を無視: %s", s)

    connectors: list[BaseConnector] = []
    for site in enabled:
        conn = registry.get(site)
        if conn is None:
            continue
        if not conn.available():
            logger.info("[%s] APIキー未設定または未対応のためスキップ", site)
            continue
        connectors.append(conn)
    return connectors


def run_search(connectors: list[BaseConnector], query: SearchQuery) -> list[Product]:
    """各コネクタを並列実行（レート制限は各コネクタ内で遵守・設計書 7.2）"""
    products: list[Product] = []
    if not connectors:
        return products
    with ThreadPoolExecutor(max_workers=len(connectors)) as pool:
        futures = {pool.submit(c.search, query): c for c in connectors}
        for future in as_completed(futures):
            conn = futures[future]
            try:
                result = future.result()
                logger.info("[%s] %d件取得", conn.name, len(result))
                products.extend(result)
            except ConnectorError as exc:
                logger.error("%s → このサイトはスキップして継続します", exc)
            except Exception as exc:  # noqa: BLE001
                logger.error("[%s] 予期しないエラー: %s → スキップして継続", conn.name, exc)
    return products


# ----------------------------------------------------------------------
def cmd_search(args: argparse.Namespace) -> int:
    config = load_config(args.config)

    query = SearchQuery(
        keyword=args.keyword,
        jan_code=args.jan,
        model_number=args.model,
        max_results=args.max,
        condition=args.condition,
    )
    try:
        query.validate_any()
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    sites_filter = args.sites.split(",") if args.sites else None
    connectors = build_connectors(config, sites_filter)
    if not connectors:
        logger.error(
            "利用可能なコネクタがありません。.env にAPIキー（RAKUTEN_APP_ID / YAHOO_APP_ID 等）を"
            "設定してください"
        )
        return 1

    logger.info("検索開始: %s（サイト: %s）", query.query_text,
                ", ".join(c.name for c in connectors))
    products = dedupe_products(run_search(connectors, query))
    if not products:
        logger.warning("検索結果 0件（設計書9章: 0件として記録し終了）")

    rows = filter_rows(build_rows(products, config), config)

    # Tier3サイトの検索リンク生成（設計書 3.1 Tier3）
    tier3_sites = list(config.get("sites", {}).get("tier3", []))
    if not config.get("sites", {}).get("tier2_scraping_enabled", False):
        # スクレイピング無効時はTier2サイトも検索リンクでカバー
        tier3_sites += [s for s in config.get("sites", {}).get("tier2", [])
                        if s not in tier3_sites]
    tier3_links = build_tier3_links(query.query_text, tier3_sites)

    # 出力（設計書 6章 / 9章: Sheets失敗時はCSV退避）
    out = args.output or config.get("output", {}).get("default", "excel")
    try:
        if out == "gsheet":
            from output.gsheet import GoogleSheetsWriter
            url = GoogleSheetsWriter(config).write(rows, tier3_links)
            print(f"\n✅ Google Sheetsに出力しました: {url}")
        elif out == "csv":
            from output.csv_fallback import write_csv
            path = write_csv(rows, BASE_DIR)
            print(f"\n✅ CSVに出力しました: {path}")
        else:
            from output.excel import ExcelWriter
            outfile = args.outfile or config.get("output", {}).get(
                "excel_path", str(BASE_DIR / "仕入れ候補.xlsx"))
            path = ExcelWriter(config, outfile).write(rows, tier3_links)
            print(f"\n✅ Excelに出力しました: {path}")
    except Exception as exc:  # noqa: BLE001
        logger.error("出力失敗: %s → CSVに退避します", exc)
        from output.csv_fallback import write_csv
        path = write_csv(rows, BASE_DIR)
        print(f"\n⚠️ 出力に失敗したためCSVへ退避しました: {path}")

    _print_summary(rows)
    return 0


def _print_summary(rows) -> None:
    from core.judge import JUDGE_ORDER
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.judgement] = counts.get(row.judgement, 0) + 1
    print(f"候補: {len(rows)}件 | " + " ".join(
        f"{k}:{counts[k]}" for k in sorted(counts, key=lambda x: JUDGE_ORDER.get(x, 9))
    ))
    top = [r for r in rows if r.judgement in ("◎", "○")][:5]
    if top:
        print("\n-- 有望候補（上位5件）--")
        for r in top:
            profit = f"{r.profit.profit:+,}円" if r.profit else "?"
            margin = f"{r.profit.margin:.0%}" if r.profit and r.profit.margin else "?"
            print(f" {r.judgement} [{r.product.source}] {r.product.title[:40]} "
                  f"仕入{r.profit.effective_cost if r.profit else r.product.price:,}円 → "
                  f"想定利益 {profit}（利益率{margin}）")
    print("\n※ 推定値は足切り用です。仕入れ判断は必ず「相場確認URL」で実勢価格を確認してから！")


# ----------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sedori-tool",
        description="仕入れ候補発掘ツール: 複数ECサイト横断検索 → メルカリ利益計算 → 判定 → スプレッドシート出力",
    )
    parser.add_argument("--config", help="config.yaml のパス", default=None)
    parser.add_argument("-v", "--verbose", action="store_true", help="デバッグログ")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="商品を検索して仕入れ候補を出力")
    p_search.add_argument("--keyword", help="検索キーワード")
    p_search.add_argument("--jan", help="JANコード")
    p_search.add_argument("--model", help="型番")
    p_search.add_argument("--max", type=int, default=20, help="サイトごとの最大取得件数")
    p_search.add_argument("--condition", choices=["new", "used", "any"], default="any")
    p_search.add_argument("--sites", help="対象サイト（カンマ区切り。例: rakuten,yahoo）")
    p_search.add_argument("--output", choices=["excel", "gsheet", "csv"],
                          help="出力先（デフォルト: config.yaml の output.default）")
    p_search.add_argument("--outfile", help="Excel出力ファイルパス")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    load_dotenv(BASE_DIR / ".env")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
