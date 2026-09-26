"""
Run a full scan and auto-fetch details on the top 5 results.
Output is saved to scan_output.txt
"""
import sys
import os
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from scanner import Scanner
from display import show_results
from rich.console import Console

output_file = open("scan_output.txt", "w", encoding="utf-8")
console = Console(file=output_file, highlight=False)

console.print("\n[bold bright_cyan]VOLATILE STOCK DISCOVERY - FULL SCAN + TOP 5 DETAIL[/bold bright_cyan]\n")

config = Config(top_n=25)
scanner = Scanner(config)

console.print("Running scan...")
results = scanner.run(deep_scan=True, top_n=25)

if not results:
    console.print("[red]No results found.[/red]")
    output_file.close()
    sys.exit(1)

show_results(results, title="Top 25 Volatile Stocks")

top5 = results[:5]
console.print(f"\n[bold cyan]--- TOP 5 DETAIL BREAKDOWNS ---[/bold cyan]\n")

from fetcher import DataFetcher
from screener import compute_ohlcv_signals, enrich_with_fundamentals
from scorer import compute_rocket_score, tier
from display import _cap
from rich.table import Table
from rich import box

fetcher = DataFetcher(config)

for stock in top5:
    ticker = stock.ticker
    console.print(f"\n[cyan]Fetching detail for [bold]{ticker}[/bold]...[/cyan]")
    ohlcv = fetcher.fetch_ohlcv_batch([ticker], period="30d")
    if ticker not in ohlcv:
        console.print(f"[red]No data for {ticker}[/red]")
        continue
    sig = compute_ohlcv_signals(ticker, ohlcv[ticker])
    if sig is None:
        console.print(f"[red]Could not compute signals for {ticker}[/red]")
        continue
    info = fetcher.fetch_ticker_info(ticker)
    enrich_with_fundamentals(sig, info)
    sig.rocket_score = compute_rocket_score(sig)

    t = Table(
        title=f"[bold bright_cyan]{ticker}  --  Signal Detail[/bold bright_cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    t.add_column("Signal",  style="cyan",    width=28)
    t.add_column("Value",   justify="right", width=18)
    t.add_column("Context", style="dim",     width=32)

    t.add_row("Rocket Score",     f"{sig.rocket_score:.1f} / 100",  tier(sig.rocket_score))
    t.add_section()
    t.add_row("Price",            f"${sig.current_price:.2f}")
    t.add_row("Change 1-Day",     f"{sig.pct_change_1d:+.2f}%")
    t.add_row("Change 5-Day",     f"{sig.pct_change_5d:+.2f}%")
    t.add_row("Change 30-Day",    f"{sig.pct_change_30d:+.2f}%")
    t.add_section()
    t.add_row("Volume Today",     f"{sig.volume_today:,}")
    t.add_row("Volume 30d Avg",   f"{sig.volume_avg_30d:,.0f}")
    t.add_row("Volume Ratio",     f"{sig.volume_ratio:.2f}x",      ">=5x is noteworthy")
    t.add_section()
    t.add_row("Price / 30d Low",  f"{sig.price_vs_30d_low:.2f}x",  ">=10x = already exploded")
    t.add_row("Price / 30d High", f"{sig.price_vs_30d_high:.2f}x", "1.0 = at 30-day high")
    t.add_row("Daily Volatility", f"{sig.daily_volatility:.2f}%",   "std-dev of daily returns")
    t.add_section()
    t.add_row("Market Cap",       _cap(sig.market_cap))
    if sig.float_shares is not None:
        t.add_row("Float Shares",  f"{sig.float_shares:,.0f}")
    if sig.float_rotation is not None:
        t.add_row("Float Rotation", f"{sig.float_rotation:.3f}x",  ">=1x = float fully turned")
    if sig.short_ratio is not None:
        t.add_row("Short Ratio",   f"{sig.short_ratio:.1f} days",   ">=10 = squeeze fuel")
    t.add_section()
    t.add_row("Already 10x'd",    "YES" if sig.already_exploded else "No")
    t.add_row("Parabolic (3x+)",  "YES" if sig.is_parabolic    else "No")

    console.print(t)

console.print("\n[dim yellow]Done. Results saved to scan_output.txt[/dim yellow]")
output_file.close()
print("Scan complete. Results saved to scan_output.txt")
