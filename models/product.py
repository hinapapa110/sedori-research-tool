"""共通商品モデル・検索クエリ（設計書 3.2 / 3.5）"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """コネクタ共通の検索条件"""

    keyword: Optional[str] = None
    jan_code: Optional[str] = None
    model_number: Optional[str] = None
    max_results: int = 20
    condition: Literal["new", "used", "any"] = "any"

    @property
    def query_text(self) -> str:
        """検索語として使う文字列（JAN > 型番 > キーワードの優先順）"""
        return self.jan_code or self.model_number or self.keyword or ""

    def validate_any(self) -> None:
        if not (self.keyword or self.jan_code or self.model_number):
            raise ValueError("keyword / jan_code / model_number のいずれかを指定してください")


class Product(BaseModel):
    """共通商品モデル（設計書 3.5）"""

    source: str                      # "amazon" / "rakuten" / "yahoo" / "ebay" / "aliexpress" / "surugaya" 等
    tier: int                        # 1: 公式API / 2: スクレイピング / 3: URLのみ
    product_id: str                  # ASIN / itemCode 等
    title: str
    url: str
    image_url: Optional[str] = None
    jan_code: Optional[str] = None
    price: int                       # 商品価格（円・税込。外貨は換算済み）
    shipping_cost: int = 0           # 仕入れ時の送料（円）※無料なら0
    condition: str = "unknown"       # new / used / refurbished / unknown
    points: int = 0                  # 楽天/Yahoo!のポイント還元（実質値引き扱い）
    is_import: bool = False          # 海外仕入れ（eBay/AliExpress/Temu）フラグ
    import_cost: int = 0             # 輸入諸経費の概算（設計書 4.6）
    currency_note: Optional[str] = None  # 元通貨・換算レート（例: "USD 12.50 @150.2"）
    fetched_at: datetime = Field(default_factory=datetime.now)
