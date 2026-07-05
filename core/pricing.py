"""想定販売価格の自動推定モジュール（設計書 3.4-① / 4.5 拡張版）

楽天/Yahoo!の同一商品の相場中央値 × 補正係数 → メルカリ想定販売価格

同一商品の判定は3段階（上から順に精度が高い）:
  1. JAN一致   … 最も確実。JAN検索時はこれが効く
  2. 型番一致   … 商品名から型番（例: WH-1000XM4）を抽出して照合
  3. 類似タイトル … ノイズ語を除去した商品名の2-gram類似度で照合（参考値扱い）

- 中央値を採用（平均値は外れ値に弱い）
- 推定ステータス: 推定OK / 参考値 / 推定不能
- 推定値はあくまで足切り用。仕入れ判断は目視確定後の値で行う
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from dataclasses import dataclass
from typing import Optional

from models.product import Product

STATUS_OK = "推定OK"
STATUS_REF = "参考値"
STATUS_NONE = "推定不能"

BASIS_JAN = "JAN一致"
BASIS_MODEL = "型番一致"
BASIS_SIMILAR = "類似"

# 型番らしきトークン: 英字+数字の組み合わせ（例: WH-1000XM4 / SD-1704 / BTE-A1000）
_MODEL_RE = re.compile(r"[A-Za-z]+[-‐]?[A-Za-z]*\d{2,}[A-Za-z0-9-]*")

# 商品名の比較で無視するノイズ語（状態・販促系）
_NOISE_WORDS = [
    "中古", "新品", "未使用", "未開封", "美品", "訳あり", "アウトレット", "整備済",
    "送料無料", "全国送料無料", "即納", "即日発送", "土日祝発送", "翌日配達",
    "ポイント", "倍", "セール", "期間限定", "限定", "特価", "予約", "レビュー特典",
    "レビューキャンペーン実施中", "クーポン", "保証", "正規品", "国内正規品",
]
_BRACKETS_RE = re.compile(r"[【】\[\]（）()「」『』<>《》]")
_SPACES_RE = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    """商品名を比較用に正規化（全角→半角・小文字化・ノイズ語除去）"""
    s = unicodedata.normalize("NFKC", title).lower()
    s = _BRACKETS_RE.sub(" ", s)
    for w in _NOISE_WORDS:
        s = s.replace(w.lower(), " ")
    s = _SPACES_RE.sub("", s)
    return s


def extract_model_tokens(title: str) -> set[str]:
    """商品名から型番らしきトークンを抽出（英字と数字を両方含む4文字以上）"""
    normalized = unicodedata.normalize("NFKC", title).upper()
    tokens = set()
    for m in _MODEL_RE.findall(normalized):
        t = m.strip("-")
        if len(t) >= 4 and any(c.isdigit() for c in t) and any(c.isalpha() for c in t):
            tokens.add(t)
    return tokens


def _bigrams(s: str) -> set[str]:
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}


def title_similarity(a: str, b: str) -> float:
    """正規化済みタイトル同士の2-gram Jaccard類似度（0〜1）"""
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


@dataclass(frozen=True)
class PriceEstimate:
    estimated_price: Optional[int]  # 推定販売価格（円）。推定不能なら None
    status: str                     # 推定OK / 参考値 / 推定不能
    sample_count: int
    reference_median: Optional[int]
    basis: str = ""                 # JAN一致 / 型番一致 / 類似

    @property
    def label(self) -> str:
        """スプレッドシート表示用（例: 推定OK(JAN一致3件)）"""
        if self.sample_count:
            return f"{self.status}({self.basis}{self.sample_count}件)"
        return self.status


class PriceEstimator:
    def __init__(self, config: dict):
        pricing = config.get("pricing", {})
        self.reference_sites: list[str] = pricing.get("reference_sites", ["rakuten", "yahoo"])
        self.adjust_factor: float = float(pricing.get("adjust_factor", 0.85))
        self.min_samples_ok: int = int(pricing.get("min_samples_ok", 3))
        self.fallback_model_match: bool = bool(pricing.get("fallback_model_match", True))
        # 0 にすると類似タイトルフォールバックを無効化
        self.similarity_threshold: float = float(pricing.get("title_similarity_threshold", 0.60))

    # ------------------------------------------------------------------
    def estimate(self, candidate: Product, all_products: list[Product]) -> PriceEstimate:
        pool = self._reference_pool(candidate, all_products)
        if not pool:
            return PriceEstimate(None, STATUS_NONE, 0, None)

        # 1) JAN一致（最優先・最も確実）
        samples = self._filter_condition(candidate, [
            p for p in pool if candidate.jan_code and p.jan_code == candidate.jan_code
        ])
        basis = BASIS_JAN

        # 2) 型番一致フォールバック
        if not samples and self.fallback_model_match:
            models = extract_model_tokens(candidate.title)
            if models:
                samples = self._filter_condition(candidate, [
                    p for p in pool if models & extract_model_tokens(p.title)
                ])
                basis = BASIS_MODEL

        # 3) 類似タイトルフォールバック（常に参考値扱い）
        if not samples and self.similarity_threshold > 0:
            norm = normalize_title(candidate.title)
            samples = self._filter_condition(candidate, [
                p for p in pool
                if title_similarity(norm, normalize_title(p.title)) >= self.similarity_threshold
            ])
            basis = BASIS_SIMILAR

        if not samples:
            return PriceEstimate(None, STATUS_NONE, 0, None)

        prices = self._drop_outliers([p.price for p in samples])
        median = int(round(statistics.median(prices)))
        estimated = int(round(median * self.adjust_factor))

        if basis == BASIS_SIMILAR:
            status = STATUS_REF  # 類似一致は件数によらず参考値
        else:
            status = STATUS_OK if len(prices) >= self.min_samples_ok else STATUS_REF
        return PriceEstimate(estimated, status, len(prices), median, basis)

    # ------------------------------------------------------------------
    def _reference_pool(self, candidate: Product, all_products: list[Product]) -> list[Product]:
        return [
            p for p in all_products
            if p.source in self.reference_sites
            and p.url != candidate.url
            and p.price > 0
        ]

    @staticmethod
    def _filter_condition(candidate: Product, pool: list[Product]) -> list[Product]:
        """同等状態（中古なら中古）のサンプルを優先。なければ全体を使う"""
        target = candidate.condition if candidate.condition in ("new", "used") else None
        if target:
            same = [p for p in pool if p.condition == target]
            if same:
                return same
        return pool

    @staticmethod
    def _drop_outliers(prices: list[int]) -> list[int]:
        """中央値から大きく外れた価格（1/3未満・3倍超）を除外（付属品・セット品対策）"""
        if len(prices) < 3:
            return prices
        med = statistics.median(prices)
        kept = [p for p in prices if med / 3 <= p <= med * 3]
        return kept or prices
