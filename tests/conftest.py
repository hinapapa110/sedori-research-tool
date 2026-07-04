import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def config() -> dict:
    """設計書デフォルト値の設定"""
    return {
        "mercari": {"fee_rate": 0.10},
        "shipping": {
            "nekopos": 210, "compact": 450, "compact_box": 70,
            "size60": 750, "size80": 850, "size100": 1050, "size120": 1200,
        },
        "materials": {"nekopos": 30, "compact": 20, "size60_80": 80, "size100_over": 150},
        "judge": {
            "strong_buy": {"profit": 1500, "margin": 0.25},
            "buy": {"profit": 800, "margin": 0.15},
            "consider": {"profit": 500, "margin": 0.10},
        },
        "limits": {"max_purchase_price": 10000},
        "points": {"include_as_discount": True},
        "import": {
            "exchange_buffer": 0.03,
            "consumption_tax": 0.10,
            "customs_valuation": 0.60,
            "duty_free_threshold": 10000,
            "simple_duty_rate": 0.05,
            "customs_handling_fee": 200,
            "risk_margin_add": 0.05,
            "fallback_rates": {"USD": 155.0},
        },
        "pricing": {
            "source": "estimate",
            "reference_sites": ["rakuten", "yahoo"],
            "adjust_factor": 0.85,
            "min_samples_ok": 3,
            "default_size": "size60",
            "mercari_search_url": "https://jp.mercari.com/search?keyword={query}&status=sold_out",
        },
        "sites": {
            "tier1": ["rakuten", "yahoo"],
            "tier2": ["surugaya"],
            "tier2_scraping_enabled": False,
            "tier3": ["yahoo_auction", "rakuma", "temu", "qoo10"],
        },
        "output": {"default": "excel", "skip_rejected": False},
    }
