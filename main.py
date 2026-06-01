#!/usr/bin/env python3
"""
Volatile Stock Discovery Tool
==============================
Finds stocks exhibiting or approaching extreme volatility / 10x price moves.

Usage:
  python main.py scan                          # scan full NASDAQ universe
  python main.py scan -t GME,AMC,NVDA          # scan specific tickers
  python main.py scan -f my_tickers.txt        # scan tickers from a file
  python main.py detail TICKER                 # deep-dive a single stock
"""

import sys

import click
from rich.console import Console

from config import Config
from display import console, show_results
from scanner import Scanner

BANNER = (
    "\n[bold bright_cyan]"
    "╔══════════════════════════════════════════╗\n"
    "║   🚀  VOLATILE STOCK DISCOVERY TOOL   🚀 ║\n"
    "║   Hunting 10x moves in real time         ║\n"
    "╚══════════════════════════════════════════╝"
    "[/bold bright_cyan]\n"
)

DISCLAIMER = (
    "\n[dim yellow]⚠  Disclaimer: For informational purposes only. "
    "Highly volatile stocks carry extreme risk of total loss. "
    "Never trade based solely on this tool.[/dim yellow]\n"
)


@click.group()
def cli():
    """Volatile Stock Discovery — find the next 10x rocket."""


@cli.command()
@click.option("--tickers", "-t", default=None, help="Comma-separated tickers, e.g. GME,AMC")
@click.option("--file", "-f", "ticker_file", default=None,
              type=click.Path(exists=True), help="File with one ticker per line")
@click.option("--top", "-n", default=25, show_default=True, help="Number of results")
@click.option("--min-price", default=0.50, show_default=True, help="Minimum price ($)")
@click.option("--max-price", default=500.0, show_default=True, help="Maximum price ($)")
@click.option("--min-volume", default=50_000, show_default=True, help="Min avg daily volume")
@click.option("--universe-size", default=3000, show_default=True,
              help="Max tickers from NASDAQ universe")
@click.option("--no-deep-scan", is_flag=True, default=False,
              help="Skip per-ticker fundamentals (faster, less accurate)")
@click.option("--no-cache", is_flag=True, default=False, help="Ignore cached data")
def scan(tickers, ticker_file, top, min_price, max_price, min_volume,
         universe_size, no_deep_scan, no_cache):
    """Scan the market for stocks with explosive volatility potential."""

    console.print(BANNER)

    config = Config(
        min_price=min_price,
        max_price=max_price,
        min_avg_volume=min_volume,
        max_universe_size=universe_size,
        top_n=top,
    )

    if no_cache:
        import shutil
        if config.cache_dir.exists():
            shutil.rmtree(config.cache_dir)
            console.print("[dim]Cache cleared.[/dim]")

    # Build ticker list
    ticker_list = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        console.print(f"[cyan]Scanning {len(ticker_list)} provided tickers.[/cyan]")
    elif ticker_file:
        with open(ticker_file) as fh:
            ticker_list = [line.strip().upper() for line in fh if line.strip()]
        console.print(f"[cyan]Loaded {len(ticker_list)} tickers from {ticker_file}.[/cyan]")

    results = Scanner(config).run(
        tickers=ticker_list,
        deep_scan=not no_deep_scan,
        top_n=top,
    )

    if not results:
        console.print("[red]No stocks found. Try --no-deep-scan or looser filters.[/red]")
        sys.exit(1)

    show_results(results, title=f"Top {len(results)} Volatile Stocks")
    console.print(DISCLAIMER)


@cli.command()
@click.argument("ticker")
@click.option("--period", "-p", default="30d", show_default=True,
              help="Lookback period: 5d, 1mo, 3mo, 6mo, 1y")
@click.option("--demo", is_flag=True, default=False,
              help="Use synthetic data (no internet required)")
def detail(ticker, period, demo):
    """Show a full signal breakdown for a single stock."""
    from screener import compute_ohlcv_signals, enrich_with_fundamentals
    from scorer import compute_rocket_score, tier
    from display import _cap
    from rich.table import Table
    from rich import box

    ticker = ticker.upper()

    if demo:
        from demo import generate_demo_results, _SEED_TICKERS
        import random
        # Find this ticker in the seed list, or generate a fresh rocket-profile signal
        profile_map = dict(_SEED_TICKERS)
        profile = profile_map.get(ticker, "rocket")
        from demo import _make_signal
        sig = _make_signal(ticker, profile, random.Random(hash(ticker) & 0xFFFF))
        sig.rocket_score = compute_rocket_score(sig)
        console.print(f"\n[dim yellow]Demo mode — showing synthetic data for {ticker}[/dim yellow]")
    else:
        from fetcher import DataFetcher
        config = Config()
        fetcher = DataFetcher(config)

        console.print(f"\n[cyan]Fetching data for [bold]{ticker}[/bold]…[/cyan]")
        ohlcv = fetcher.fetch_ohlcv_batch([ticker], period=period)

        if ticker not in ohlcv:
            console.print(f"[red]No data for {ticker}. Check the ticker symbol.[/red]")
            console.print("[dim]Tip: use --demo to preview with synthetic data.[/dim]")
            sys.exit(1)

        sig = compute_ohlcv_signals(ticker, ohlcv[ticker])
        if sig is None:
            console.print(f"[red]Could not compute signals for {ticker}.[/red]")
            sys.exit(1)

        console.print("[cyan]Fetching fundamentals…[/cyan]")
        info = fetcher.fetch_ticker_info(ticker)
        enrich_with_fundamentals(sig, info)
        sig.rocket_score = compute_rocket_score(sig)

    t = Table(
        title=f"[bold bright_cyan]{ticker}  —  Signal Detail[/bold bright_cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    t.add_column("Signal",  style="cyan",       width=28)
    t.add_column("Value",   justify="right",    width=18)
    t.add_column("Context", style="dim",        width=32)

    def row(name, val, ctx=""):
        t.add_row(name, val, ctx)

    row("Rocket Score",     f"{sig.rocket_score:.1f} / 100",  tier(sig.rocket_score))
    t.add_section()
    row("Price",            f"${sig.current_price:.2f}")
    row("Change 1-Day",     f"{sig.pct_change_1d:+.2f}%")
    row("Change 5-Day",     f"{sig.pct_change_5d:+.2f}%")
    row("Change 30-Day",    f"{sig.pct_change_30d:+.2f}%")
    t.add_section()
    row("Volume Today",     f"{sig.volume_today:,}")
    row("Volume 30d Avg",   f"{sig.volume_avg_30d:,.0f}")
    row("Volume Ratio",     f"{sig.volume_ratio:.2f}×",     "≥5× is noteworthy")
    t.add_section()
    row("Price / 30d Low",  f"{sig.price_vs_30d_low:.2f}×", "≥10× = already exploded")
    row("Price / 30d High", f"{sig.price_vs_30d_high:.2f}×","1.0 = at 30-day high")
    row("Daily Volatility", f"{sig.daily_volatility:.2f}%",  "std-dev of daily returns")
    t.add_section()
    row("Market Cap",       _cap(sig.market_cap))
    if sig.float_shares is not None:
        row("Float Shares",  f"{sig.float_shares:,.0f}")
    if sig.float_rotation is not None:
        row("Float Rotation", f"{sig.float_rotation:.3f}×", "≥1× = float fully turned")
    if sig.short_ratio is not None:
        row("Short Ratio",   f"{sig.short_ratio:.1f} days",  "≥10 = squeeze fuel")
    t.add_section()
    row("Already 10×'d",    "✓ YES" if sig.already_exploded else "✗ No")
    row("Parabolic (3×+)",  "✓ YES" if sig.is_parabolic    else "✗ No")

    console.print(t)
    console.print(
        f"\n[dim]Chart → https://finance.yahoo.com/chart/{ticker}[/dim]\n"
    )


@cli.command()
@click.option("--top", "-n", default=25, show_default=True, help="Number of results")
@click.option("--seed", default=42, show_default=True, help="Random seed for reproducibility")
def demo(top, seed):
    """Preview the tool with synthetic data (no internet required)."""
    from demo import generate_demo_results

    console.print(BANNER)
    console.print("[dim yellow]⚠  Demo mode — data is synthetic, not real market data.[/dim yellow]\n")

    results = generate_demo_results(top_n=top, seed=seed)
    show_results(results, title=f"DEMO — Top {len(results)} Volatile Stocks")
    console.print(DISCLAIMER)


if __name__ == "__main__":
    cli()
