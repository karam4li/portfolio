"""
Orchestrates the two-pass scanning pipeline:
  Pass 1 — batch OHLCV download → fast signal computation → pre-filter
  Pass 2 — per-ticker .info fetch on top candidates → enrich → re-score
"""

from typing import List, Optional

from rich.console import Console

from config import Config
from display import make_progress
from fetcher import DataFetcher
from screener import (
    StockSignals,
    compute_ohlcv_signals,
    enrich_with_fundamentals,
    passes_prefilter,
)
from scorer import compute_rocket_score
from universe import load_us_stocks

console = Console()


class Scanner:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.fetcher = DataFetcher(self.config)

    def run(
        self,
        tickers: Optional[List[str]] = None,
        deep_scan: bool = True,
        top_n: int | None = None,
    ) -> List[StockSignals]:

        top_n = top_n or self.config.top_n

        # ── Step 1: Universe ──────────────────────────────────────────────
        if tickers is None:
            console.print("[cyan]Loading stock universe…[/cyan]")
            tickers = load_us_stocks(self.config.max_universe_size)
            console.print(f"[dim]  {len(tickers)} tickers loaded[/dim]")

        # ── Step 2: Batch OHLCV → fast signals ───────────────────────────
        all_signals: List[StockSignals] = []
        batches = [
            tickers[i : i + self.config.batch_size]
            for i in range(0, len(tickers), self.config.batch_size)
        ]

        with make_progress() as prog:
            task = prog.add_task(
                f"[cyan]Scanning {len(tickers)} tickers…[/cyan]",
                total=len(batches),
            )
            for batch in batches:
                ohlcv = self.fetcher.fetch_ohlcv_batch(batch, period="30d")
                for ticker, df in ohlcv.items():
                    sig = compute_ohlcv_signals(ticker, df)
                    if sig is None:
                        continue
                    if not (self.config.min_price <= sig.current_price <= self.config.max_price):
                        continue
                    if sig.volume_avg_30d < self.config.min_avg_volume:
                        continue
                    all_signals.append(sig)
                prog.advance(task)

        console.print(f"[dim]  {len(all_signals)} stocks passed basic filters[/dim]")

        if not all_signals:
            return []

        # ── Step 3: Pre-score, pick deep-scan candidates ─────────────────
        for s in all_signals:
            s.rocket_score = compute_rocket_score(s)

        all_signals.sort(key=lambda s: s.rocket_score, reverse=True)

        # ── Step 4: Deep scan — fetch per-ticker fundamentals ─────────────
        if deep_scan:
            candidates = [s for s in all_signals if passes_prefilter(s, self.config)]
            candidates = candidates[: self.config.top_candidates_for_deep_scan]

            if candidates:
                console.print(
                    f"[cyan]Deep-scanning {len(candidates)} top candidates…[/cyan]"
                )
                with make_progress() as prog:
                    task = prog.add_task(
                        "[cyan]Fetching fundamentals…[/cyan]",
                        total=len(candidates),
                    )
                    for s in candidates:
                        info = self.fetcher.fetch_ticker_info(s.ticker)
                        enrich_with_fundamentals(s, info)
                        s.rocket_score = compute_rocket_score(s)
                        prog.advance(task)

        # ── Step 5: Final sort + trim ─────────────────────────────────────
        all_signals.sort(key=lambda s: s.rocket_score, reverse=True)
        return all_signals[:top_n]
