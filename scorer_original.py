"""
Composite rocket score (0–100) that ranks stocks by 10x-move likelihood.

Weight breakdown:
  35% volume spike        — the single biggest predictor of explosive moves
  25% intraday price move — already in motion
  20% float rotation      — when the float turns over, the move is real
  10% 30-day momentum     — sustained multi-week run
   5% short squeeze setup — squeeze fuel (days-to-cover)
   5% small-cap bonus     — micro/small caps move faster
"""

import math
from screener import StockSignals


def compute_rocket_score(s: StockSignals) -> float:
    score = 0.0

    # 1. Volume spike (0–35 pts)
    #    10x volume  → ~27 pts,  20x volume → 35 pts
    if s.volume_ratio > 1:
        score += min(35.0, (math.log(s.volume_ratio) / math.log(20)) * 35)

    # 2. Intraday move (0–25 pts)
    #    10% move → ~14 pts,  50% move → 25 pts
    move = max(s.pct_change_1d, 0.0)
    if move > 0:
        score += min(25.0, (math.log(move + 1) / math.log(51)) * 25)

    # 3. Float rotation (0–20 pts) — float turned over = conviction
    if s.float_rotation is not None and s.float_rotation > 0:
        score += min(20.0, (math.log(s.float_rotation * 2 + 1) / math.log(5)) * 20)
    else:
        # No float data: grant partial proxy credit from volume alone
        score += min(8.0, (math.log(max(s.volume_ratio, 1)) / math.log(20)) * 8)

    # 4. 30-day momentum (0–10 pts)
    month_move = max(s.pct_change_30d, 0.0)
    if month_move > 0:
        score += min(10.0, (math.log(month_move + 1) / math.log(1001)) * 10)

    # 5. Short squeeze fuel (0–5 pts) — >10 days to cover is meaningful
    if s.short_ratio is not None and s.short_ratio > 3:
        score += min(5.0, (s.short_ratio / 20) * 5)

    # 6. Already-running bonus
    if s.already_exploded:
        score += 5.0
    elif s.is_parabolic:
        score += 2.0

    # 7. Small-cap bonus (easier to 10x a $100M stock than a $10B one)
    if s.market_cap is not None:
        if s.market_cap < 1e8:        # < $100M
            score += 5.0
        elif s.market_cap < 5e8:      # < $500M
            score += 3.0
        elif s.market_cap < 2e9:      # < $2B
            score += 1.0

    return round(min(score, 100.0), 1)


def tier(score: float) -> str:
    if score >= 75:
        return "🚀 ROCKET"
    if score >= 55:
        return "⚡ ELECTRIC"
    if score >= 35:
        return "🔥 HOT"
    if score >= 20:
        return "📈 RISING"
    return "😴 QUIET"
