"""検索URL生成モジュール（設計書 3.4-② / Tier3）

- メルカリ売り切れ検索URL: 有望候補の相場を1クリックで目視確認
- Tier3サイト（ヤフオク/ラクマ/Temu/Qoo10等）の検索URL生成
"""
from __future__ import annotations

from urllib.parse import quote

DEFAULT_MERCARI_TEMPLATE = "https://jp.mercari.com/search?keyword={query}&status=sold_out"

# Tier3 + Tier2フォールバック用の検索URLテンプレート
SITE_SEARCH_URLS: dict[str, tuple[str, str]] = {
    # key: (表示名, URLテンプレート)
    "yahoo_auction": ("ヤフオク", "https://auctions.yahoo.co.jp/search/search?p={query}"),
    "rakuma": ("ラクマ", "https://fril.jp/s?query={query}"),
    "temu": ("Temu", "https://www.temu.com/search_result.html?search_key={query}"),
    "qoo10": ("Qoo10", "https://www.qoo10.jp/s/?keyword={query}"),
    "surugaya": ("駿河屋", "https://www.suruga-ya.jp/search?search_word={query}"),
    "bookoff": ("ブックオフ", "https://shopping.bookoff.co.jp/search/keyword/{query}"),
    "hardoff": ("ハードオフ", "https://netmall.hardoff.co.jp/search/?q={query}"),
    "yodobashi": ("ヨドバシ.com", "https://www.yodobashi.com/?word={query}"),
    "secondstreet": ("セカンドストリート", "https://www.2ndstreet.jp/search?keyword={query}"),
}


def mercari_soldout_url(query: str, config: dict | None = None) -> str:
    """メルカリ売り切れ検索URLを生成する（設計書 3.4-②）"""
    template = DEFAULT_MERCARI_TEMPLATE
    if config:
        template = config.get("pricing", {}).get("mercari_search_url", template)
    return template.format(query=quote(query))


def site_search_url(site_key: str, query: str) -> str:
    """Tier3/フォールバック用の検索URLを生成する"""
    if site_key not in SITE_SEARCH_URLS:
        raise KeyError(f"未知のサイト: {site_key}（有効: {list(SITE_SEARCH_URLS)}）")
    _, template = SITE_SEARCH_URLS[site_key]
    return template.format(query=quote(query))


def site_label(site_key: str) -> str:
    return SITE_SEARCH_URLS[site_key][0] if site_key in SITE_SEARCH_URLS else site_key


def build_tier3_links(query: str, site_keys: list[str]) -> list[dict]:
    """Tier3サイトの検索リンク一覧を生成（スプレッドシートの検索リンクシート用）"""
    links = []
    for key in site_keys:
        if key in SITE_SEARCH_URLS:
            links.append({
                "site": site_label(key),
                "site_key": key,
                "query": query,
                "url": site_search_url(key, query),
            })
    return links
