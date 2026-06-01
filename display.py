"""Rich terminal display for scan results."""

import io
import sys
from typing import List

from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table
from rich.text import Text

from screener import StockSignals
from scorer import tier

_out = (
    io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "buffer")
    else sys.stdout
)
console = Console(file=_out, legacy_windows=False)


# ----------------------------------------------------------------- formatters

def _pct(val: float) -> Text:
    s = f"{val:+.1f}%"
    if val >= 50:
        return Text(s, style="bold bright_green")
    if val >= 10:
        return Text(s, style="green")
    if val >= 0:
        return Text(s, style="dim green")
    if val <= -20:
        return Text(s, style="bold bright_red")
    if val <= -5:
        return Text(s, style="red")
    return Text(s, style="dim red")


def _vol_ratio(r: float) -> Text:
    s = f"{r:.1f}x"
    if r >= 20:
        return Text(s, style="bold bright_magenta")
    if r >= 10:
        return Text(s, style="bold magenta")
    if r >= 5:
        return Text(s, style="cyan")
    if r >= 2:
        return Text(s, style="white")
    return Text(s, style="dim white")


def _cap(val: float | None) -> str:
    if val is None:
        return "—"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.0f}M"
    return f"${val/1e3:.0f}K"


def _score_bar(score: float) -> Text:
    filled = round(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    label = f"{score:5.1f} {bar}"
    if score >= 75:
        return Text(label, style="bold bright_green")
    if score >= 55:
        return Text(label, style="bold yellow")
    if score >= 35:
        return Text(label, style="cyan")
    return Text(label, style="dim white")


# ---------------------------------------------------------------- main table

def show_results(results: List[StockSignals], title: str = "Volatile Stock Scanner") -> None:
    table = Table(
        title=f"\n[bold bright_cyan]{title}[/bold bright_cyan]",
        box=box.DOUBLE_EDGE,
        header_style="bold cyan",
        row_styles=["", "dim"],
    )

    table.add_column("#",        style="dim",        width=3,  justify="right")
    table.add_column("Ticker",   style="bold white", width=6)
    table.add_column("Tier",                         width=12)
    table.add_column("Score",                        width=20)
    table.add_column("Price",                        width=8,  justify="right")
    table.add_column("1D",                           width=7,  justify="right")
    table.add_column("5D",                           width=7,  justify="right")
    table.add_column("30D",                          width=8,  justify="right")
    table.add_column("Vol×",                         width=7,  justify="right")
    table.add_column("Cap",                          width=8,  justify="right")
    table.add_column("Flt×",                         width=6,  justify="right")

    for i, s in enumerate(results, 1):
        fr = f"{s.float_rotation:.2f}x" if s.float_rotation is not None else "—"
        table.add_row(
            str(i),
            s.ticker,
            tier(s.rocket_score),
            _score_bar(s.rocket_score),
            f"${s.current_price:.2f}",
            _pct(s.pct_change_1d),
            _pct(s.pct_change_5d),
            _pct(s.pct_change_30d),
            _vol_ratio(s.volume_ratio),
            _cap(s.market_cap),
            fr,
        )

    console.print(table)

    rockets  = sum(1 for s in results if s.rocket_score >= 75)
    electric = sum(1 for s in results if 55 <= s.rocket_score < 75)
    console.print(
        f"\n[dim]Showing [bold bright_green]{rockets} ROCKETS[/bold bright_green] and "
        f"[bold yellow]{electric} ELECTRIC[/bold yellow] candidates "
        f"from {len(results)} top results.[/dim]\n"
    )


# ------------------------------------------------------------ progress helper

def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    )
