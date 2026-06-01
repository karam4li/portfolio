"""
Signal computation layer.

Two passes:
  1. compute_ohlcv_signals()  — fast, runs on every ticker from batch OHLCV data
  2. enrich_with_fundamentals() — slow, runs only on pre-filtered candidates

A stock is flagged as:
  - already_exploded  if it is trading 10x+ above its 30-day low
  - is_parabolic      if it is trading 3x+ above its 30-day low
"""

from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd


@dataclass
class StockSignals:
    ticker: str
    current_price: float = 0.0

    # Price momentum
    pct_change_1d: float = 0.0
    pct_change_5d: float = 0.0
    pct_change_30d: float = 0.0

    # Volume
    volume_today: int = 0
    volume_avg_30d: float = 0.0
    volume_ratio: float = 0.0    # today's volume / 30-day average

    # Price range context
    price_vs_30d_low: float = 1.0   # current / 30-day low
    price_vs_30d_high: float = 1.0  # current / 30-day high

    # Volatility
    daily_volatility: float = 0.0   # std-dev of daily returns, as a %

    # Fundamentals — filled in by enrich_with_fundamentals()
    market_cap: Optional[float] = None
    float_shares: Optional[float] = None
    float_rotation: Optional[float] = None  # volume_today / float_shares
    short_ratio: Optional[float] = None     # days to cover short interest

    # Composite score — computed by scorer.py
    rocket_score: float = 0.0

    # Flags
    already_exploded: bool = False  # 10x+ from 30-day low
    is_parabolic: bool = False      # 3x+ from 30-day low


def compute_ohlcv_signals(ticker: str, df: pd.DataFrame) -> Optional[StockSignals]:
    """Derive price and volume signals from a 30-day daily OHLCV DataFrame."""
    if df is None or len(df) < 5:
        return None

    try:
        if isinstance(df.columns, pd.MultiIndex):
            df = df.droplevel(0, axis=1)

        close = df["Close"].dropna()
        volume = df["Volume"].dropna()

        if close.empty or len(close) < 2:
            return None

        current = float(close.iloc[-1])
        if current <= 0:
            return None

        # Returns
        pct_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100)
        pct_5d = float((close.iloc[-1] / close.iloc[max(-6, -len(close))] - 1) * 100)
        pct_30d = float((close.iloc[-1] / close.iloc[0] - 1) * 100)

        # Volume
        vol_today = int(volume.iloc[-1]) if not volume.empty else 0
        vol_prior = volume.iloc[:-1]
        vol_avg = float(vol_prior.mean()) if len(vol_prior) > 0 else float(vol_today)
        vol_ratio = (vol_today / vol_avg) if vol_avg > 0 else 1.0

        # Price range
        low_30d = float(close.min())
        high_30d = float(close.max())
        vs_low = current / low_30d if low_30d > 0 else 1.0
        vs_high = current / high_30d if high_30d > 0 else 1.0

        # Volatility (std of daily % returns)
        daily_vol = float(close.pct_change().dropna().std() * 100)

        return StockSignals(
            ticker=ticker,
            current_price=current,
            pct_change_1d=pct_1d,
            pct_change_5d=pct_5d,
            pct_change_30d=pct_30d,
            volume_today=vol_today,
            volume_avg_30d=vol_avg,
            volume_ratio=vol_ratio,
            price_vs_30d_low=vs_low,
            price_vs_30d_high=vs_high,
            daily_volatility=daily_vol,
            already_exploded=vs_low >= 10.0,
            is_parabolic=vs_low >= 3.0,
        )

    except Exception:
        return None


def enrich_with_fundamentals(signals: StockSignals, info: Dict) -> StockSignals:
    """Attach market cap, float, and short interest to an existing StockSignals."""
    if not info:
        return signals

    if (mc := info.get("marketCap")) is not None:
        signals.market_cap = float(mc)

    if (fs := info.get("floatShares")) is not None:
        signals.float_shares = float(fs)
        if signals.volume_today > 0 and fs > 0:
            signals.float_rotation = signals.volume_today / fs

    if (sr := info.get("shortRatio")) is not None:
        signals.short_ratio = float(sr)

    return signals


def passes_prefilter(signals: StockSignals, config) -> bool:
    """True if a stock is interesting enough to warrant fetching its .info."""
    return (
        signals.volume_ratio >= config.prefilter_volume_ratio
        or abs(signals.pct_change_1d) >= config.prefilter_price_move
        or signals.is_parabolic
    )
