"""Tier3サイトの検索URL生成（設計書 3.1 Tier3）

ヤフオク / ラクマ / Temu / Qoo10 などは自動取得せず、
絞り込み検索URLを生成してスプレッドシートに埋め込み、目視確認を高速化する。
実装は core/url_builder.py に集約している。
"""
from __future__ import annotations

from core.url_builder import build_tier3_links, site_label, site_search_url

__all__ = ["build_tier3_links", "site_label", "site_search_url"]
