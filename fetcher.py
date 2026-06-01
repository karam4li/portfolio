"""
Data fetching layer.  Wraps yfinance with simple disk-based caching so
repeated runs during the same session don't hammer Yahoo Finance.
"""

import pickle
import time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from config import Config


class DataFetcher:
    def __init__(self, config: Config):
        self.config = config
        self.cache_dir = config.cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    # ------------------------------------------------------------------ cache

    def _cache_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() else "_" for c in key)
        return self.cache_dir / f"{safe[:80]}.pkl"

    def _load_cache(self, key: str):
        path = self._cache_path(key)
        if path.exists():
            age_secs = time.time() - path.stat().st_mtime
            if age_secs < self.config.cache_ttl_minutes * 60:
                try:
                    with open(path, "rb") as f:
                        return pickle.load(f)
                except Exception:
                    pass
        return None

    def _save_cache(self, key: str, data) -> None:
        path = self._cache_path(key)
        with open(path, "wb") as f:
            pickle.dump(data, f)

    # --------------------------------------------------------------- OHLCV

    def fetch_ohlcv_batch(
        self, tickers: List[str], period: str = "30d"
    ) -> Dict[str, pd.DataFrame]:
        """
        Batch-download daily OHLCV for a list of tickers.
        Returns a dict of {ticker: DataFrame}.
        """
        if not tickers:
            return {}

        cache_key = f"ohlcv_{period}_{'_'.join(sorted(tickers))}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        try:
            raw = yf.download(
                " ".join(tickers),
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                group_by="ticker",
            )
        except Exception:
            return {}

        result: Dict[str, pd.DataFrame] = {}

        if len(tickers) == 1:
            if raw is not None and not raw.empty:
                if isinstance(raw.columns, pd.MultiIndex):
                    df = raw[tickers[0]].dropna(how="all")
                    if not df.empty:
                        result[tickers[0]] = df
                else:
                    result[tickers[0]] = raw
        else:
            if raw is None or raw.empty:
                return {}
            for ticker in tickers:
                try:
                    lvl0 = raw.columns.get_level_values(0)
                    if ticker in lvl0:
                        df = raw[ticker].dropna(how="all")
                        if not df.empty:
                            result[ticker] = df
                except Exception:
                    pass

        self._save_cache(cache_key, result)
        return result

    # ----------------------------------------------------------------- info

    def fetch_ticker_info(self, ticker: str) -> Dict:
        """Fetch fundamental/metadata for a single ticker via yfinance .info."""
        cache_key = f"info_{ticker}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        try:
            info = yf.Ticker(ticker).info or {}
            self._save_cache(cache_key, info)
            return info
        except Exception:
            return {}
