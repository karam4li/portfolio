"""
Demo mode: generates realistic synthetic stock data so the tool can be
previewed in environments without live Yahoo Finance access.
"""

import random
from typing import List

from screener import StockSignals
from scorer import compute_rocket_score


_SEED_TICKERS = [
    # Known volatile / meme / small-cap names
    ("GME",  "rocket"),
    ("AMC",  "rocket"),
    ("MARA", "rocket"),
    ("RIOT", "electric"),
    ("COIN", "electric"),
    ("PLTR", "hot"),
    ("LCID", "hot"),
    ("NVAX", "hot"),
    ("SNDL", "rising"),
    ("CLOV", "rising"),
    ("SPCE", "hot"),
    ("BBIG", "rocket"),
    ("PROG", "electric"),
    ("IRNT", "rocket"),
    ("SPRT", "rocket"),
    ("TMC",  "rising"),
    ("OPAD", "electric"),
    ("NKLA", "rising"),
    ("WKHS", "hot"),
    ("RIDE", "rising"),
    ("FSR",  "hot"),
    ("XPEV", "hot"),
    ("NIO",  "hot"),
    ("TSLA", "electric"),
    ("NVDA", "rising"),
]


def _make_signal(ticker: str, profile: str, rng: random.Random) -> StockSignals:
    """Build a StockSignals instance with plausible values for the given profile."""

    if profile == "rocket":
        price         = rng.uniform(1.0, 15.0)
        pct_1d        = rng.uniform(40, 120)
        pct_5d        = rng.uniform(80, 300)
        pct_30d       = rng.uniform(150, 900)
        vol_ratio     = rng.uniform(12, 40)
        vol_avg       = rng.randint(500_000, 5_000_000)
        market_cap    = rng.uniform(30e6, 300e6)
        float_rot     = rng.uniform(0.8, 3.5)
        short_ratio   = rng.uniform(4, 18)
    elif profile == "electric":
        price         = rng.uniform(5, 50)
        pct_1d        = rng.uniform(15, 45)
        pct_5d        = rng.uniform(30, 100)
        pct_30d       = rng.uniform(50, 200)
        vol_ratio     = rng.uniform(5, 15)
        vol_avg       = rng.randint(200_000, 3_000_000)
        market_cap    = rng.uniform(100e6, 800e6)
        float_rot     = rng.uniform(0.2, 1.0)
        short_ratio   = rng.uniform(2, 10)
    elif profile == "hot":
        price         = rng.uniform(3, 100)
        pct_1d        = rng.uniform(5, 18)
        pct_5d        = rng.uniform(10, 50)
        pct_30d       = rng.uniform(20, 80)
        vol_ratio     = rng.uniform(2.5, 6)
        vol_avg       = rng.randint(100_000, 2_000_000)
        market_cap    = rng.uniform(200e6, 2e9)
        float_rot     = rng.uniform(0.05, 0.3)
        short_ratio   = rng.uniform(1, 5)
    else:  # rising
        price         = rng.uniform(2, 200)
        pct_1d        = rng.uniform(2, 8)
        pct_5d        = rng.uniform(5, 20)
        pct_30d       = rng.uniform(8, 35)
        vol_ratio     = rng.uniform(1.5, 3)
        vol_avg       = rng.randint(50_000, 1_000_000)
        market_cap    = rng.uniform(50e6, 1e9)
        float_rot     = rng.uniform(0.01, 0.1)
        short_ratio   = rng.uniform(0.5, 3)

    vol_today = int(vol_avg * vol_ratio)

    s = StockSignals(
        ticker=ticker,
        current_price=round(price, 2),
        pct_change_1d=round(pct_1d, 2),
        pct_change_5d=round(pct_5d, 2),
        pct_change_30d=round(pct_30d, 2),
        volume_today=vol_today,
        volume_avg_30d=vol_avg,
        volume_ratio=round(vol_ratio, 2),
        price_vs_30d_low=round(1 + pct_30d / 100, 2),
        price_vs_30d_high=round(rng.uniform(0.88, 1.0), 3),
        daily_volatility=round(rng.uniform(3, 15), 2),
        market_cap=market_cap,
        float_shares=market_cap / price * rng.uniform(0.3, 0.8),
        float_rotation=round(float_rot, 3),
        short_ratio=round(short_ratio, 1),
        already_exploded=pct_30d >= 900,
        is_parabolic=pct_30d >= 200,
    )
    s.rocket_score = compute_rocket_score(s)
    return s


def generate_demo_results(top_n: int = 25, seed: int = 42) -> List[StockSignals]:
    """Return a ranked list of synthetic StockSignals for demo purposes."""
    rng = random.Random(seed)
    results = [_make_signal(t, p, rng) for t, p in _SEED_TICKERS[:top_n]]
    results.sort(key=lambda s: s.rocket_score, reverse=True)
    return results[:top_n]
