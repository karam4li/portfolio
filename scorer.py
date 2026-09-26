"""
Early Detection Score (0–100) — finds stocks at the BEGINNING of a big move,
not ones that have already exploded.

Philosophy: volume precedes price. The ideal signal is a stock that was
completely quiet for 30 days, then woke up TODAY with a massive volume spike
and a moderate (not massive) price move. That's day 1. We want day 1.

Weight breakdown:
  30 pts  volume spike freshness  — big volume TODAY vs the sleepy baseline
  20 pts  move freshness          — how much of the 5d move happened today
  15 pts  price position          — still near 30d low = room to run
  15 pts  pre-breakout sleep      — stock was dead before today (low prior vol)
  10 pts  short squeeze fuel      — high days-to-cover = potential squeeze
   5 pts  small-cap bonus         — micro caps move faster
   5 pts  intraday move size      — some price confirmation needed

Penalties:
  -15 pts  already parabolic (3x+ from 30d low) — late
  -25 pts  already exploded (10x+ from 30d low) — very late
"""

import math
from screener import StockSignals


def compute_rocket_score(s: StockSignals) -> float:
    score = 0.0

    # ------------------------------------------------------------------
    # 1. VOLUME SPIKE FRESHNESS (0–30 pts)
    #    Big volume vs sleepy baseline. Log-scaled so 10x → ~22pts, 50x → 30pts.
    #    This is the primary signal — a massive volume spike on a previously
    #    quiet stock is the strongest early indicator.
    # ------------------------------------------------------------------
    if s.volume_ratio > 1:
        score += min(30.0, (math.log(s.volume_ratio) / math.log(50)) * 30)

    # ------------------------------------------------------------------
    # 2. MOVE FRESHNESS (0–20 pts)
    #    What fraction of the 5-day move happened TODAY?
    #    If today accounts for most of the 5d gain, this is day 1 of the move.
    #    If 5d is flat or negative, treat as neutral (0 pts).
    # ------------------------------------------------------------------
    move_1d = max(s.pct_change_1d, 0.0)
    move_5d = max(s.pct_change_5d, 0.0)

    if move_5d > 2.0 and move_1d > 0:
        # Ratio of today's move to the 5-day move (capped at 1.0)
        freshness = min(1.0, move_1d / move_5d)
        score += freshness * 20.0
    elif move_1d > 2.0 and move_5d <= 2.0:
        # Big 1d move with flat/negative 5d history — strong day-1 signal
        score += 20.0

    # ------------------------------------------------------------------
    # 3. PRICE POSITION — ROOM TO RUN (0–15 pts)
    #    Stock near its 30d low = early. Stock near its 30d high = late.
    #    We use price_vs_30d_high: 1.0 = at the 30d high (late), < 1.0 = room.
    #    Score is highest when price is well below the 30d high.
    # ------------------------------------------------------------------
    if s.price_vs_30d_high is not None and s.price_vs_30d_high > 0:
        # headroom = how far below the 30d high (0 = at high, 0.5 = 50% below)
        headroom = max(0.0, 1.0 - s.price_vs_30d_high)
        score += min(15.0, headroom * 60)   # 25% below high → 15 pts

    # ------------------------------------------------------------------
    # 4. PRE-BREAKOUT SLEEP (0–15 pts)
    #    Was the stock dormant before today? Low prior avg volume on a small
    #    float = sleeping giant. We measure this as: if volume_ratio is huge
    #    but 30d momentum is LOW, the stock was asleep and just woke up.
    #    Low 30d momentum + high volume spike = textbook early breakout.
    # ------------------------------------------------------------------
    month_move = abs(s.pct_change_30d)
    if s.volume_ratio > 3:
        if month_move < 10:
            # Very quiet 30d + huge volume today = strong sleep signal
            score += 15.0
        elif month_move < 30:
            score += 10.0
        elif month_move < 60:
            score += 5.0
        # > 60% 30d move = already been running, no sleep bonus

    # ------------------------------------------------------------------
    # 5. SHORT SQUEEZE FUEL (0–10 pts)
    #    High days-to-cover = short interest hasn't been squeezed yet.
    #    This is a LEADING indicator — squeeze is still coming.
    # ------------------------------------------------------------------
    if s.short_ratio is not None:
        if s.short_ratio >= 10:
            score += 10.0
        elif s.short_ratio >= 5:
            score += 7.0
        elif s.short_ratio >= 3:
            score += 4.0
        elif s.short_ratio >= 1:
            score += 2.0

    # ------------------------------------------------------------------
    # 6. SMALL-CAP BONUS (0–5 pts)
    #    Micro/small caps have thinner liquidity — moves are amplified.
    # ------------------------------------------------------------------
    if s.market_cap is not None:
        if s.market_cap < 5e7:          # < $50M — micro cap
            score += 5.0
        elif s.market_cap < 2e8:        # < $200M — small cap
            score += 3.0
        elif s.market_cap < 5e8:        # < $500M
            score += 1.0

    # ------------------------------------------------------------------
    # 7. INTRADAY MOVE CONFIRMATION (0–5 pts)
    #    Some price move is needed to confirm the volume isn't noise.
    #    But we want MODERATE moves here, not massive ones.
    #    A 10–30% move is ideal. Over 100% and we're likely late.
    # ------------------------------------------------------------------
    if 3 < move_1d <= 30:
        score += min(5.0, (move_1d / 30) * 5)
    elif 30 < move_1d <= 80:
        score += 3.0   # moving but getting extended
    elif move_1d > 80:
        score += 1.0   # already flying — late confirmation

    # ------------------------------------------------------------------
    # PENALTIES — already-running stocks
    # ------------------------------------------------------------------
    if s.already_exploded:
        score -= 25.0   # 10x+ from 30d low — extremely late
    elif s.is_parabolic:
        score -= 15.0   # 3x+ from 30d low — already well extended

    return round(max(0.0, min(score, 100.0)), 1)


def tier(score: float) -> str:
    if score >= 70:
        return "🌅 EARLY ROCKET"
    if score >= 50:
        return "👀 WATCH NOW"
    if score >= 30:
        return "📡 ON RADAR"
    if score >= 15:
        return "💤 TOO EARLY"
    return "😴 QUIET"
