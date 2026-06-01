from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # Price filters
    min_price: float = 0.50
    max_price: float = 500.0

    # Volume filters
    min_avg_volume: int = 50_000

    # Pre-filter before fetching per-ticker fundamentals
    prefilter_volume_ratio: float = 1.5   # must be at least 1.5x avg volume
    prefilter_price_move: float = 2.0     # or at least 2% move

    # Universe
    max_universe_size: int = 3000
    batch_size: int = 200
    top_candidates_for_deep_scan: int = 100  # run .info only on these

    # Cache
    cache_dir: Path = Path(".cache")
    cache_ttl_minutes: int = 30

    # Results
    top_n: int = 25
