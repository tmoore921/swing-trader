"""Position sizing and R:R calculations."""

import pandas as pd
from config import ACCOUNT_SIZE, RISK_PER_TRADE, MIN_RR, PREFERRED_RR, MAX_POSITION_PCT
from src.data_provider import get_history


def calculate_position(
    entry: float,
    stop: float,
    t1: float | None = None,
    t2: float | None = None,
) -> dict:
    """Return full position sizing and R:R data."""
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"valid": False, "reason": "stop_at_or_above_entry"}

    shares = RISK_PER_TRADE / risk_per_share
    position_size = shares * entry
    position_pct = position_size / ACCOUNT_SIZE * 100

    rr_t1 = round((t1 - entry) / risk_per_share, 2) if t1 and t1 > entry else None
    rr_t2 = round((t2 - entry) / risk_per_share, 2) if t2 and t2 > entry else None

    return {
        "valid": True,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "risk_per_share": round(risk_per_share, 2),
        "dollar_risk": round(RISK_PER_TRADE, 2),
        "shares": round(shares, 4),
        "position_size": round(position_size, 2),
        "position_pct_of_account": round(position_pct, 1),
        "t1": round(t1, 2) if t1 else None,
        "t2": round(t2, 2) if t2 else None,
        "rr_t1": rr_t1,
        "rr_t2": rr_t2,
        "meets_min_rr": bool(rr_t1 and rr_t1 >= MIN_RR),
        "meets_preferred_rr": bool(rr_t1 and rr_t1 >= PREFERRED_RR),
        "oversized_warning": position_pct > MAX_POSITION_PCT * 100,
    }


def estimate_targets(
    ticker: str, entry: float, stop: float, df: pd.DataFrame | None = None
) -> tuple[float | None, float | None]:
    """Estimate T1/T2 from recent swing highs as a starting point for agent review."""
    try:
        hist = df if df is not None else get_history(ticker, outputsize=300)
        if hist is None:
            raise ValueError("no data")
        high = hist["High"].astype(float)

        # T1: nearest significant resistance above entry
        recent_highs = high.iloc[-60:].values
        above = sorted([h for h in recent_highs if h > entry * 1.02])
        t1 = float(above[0]) if above else round(entry + (entry - stop) * 2, 2)

        # T2: 52-week high area as major resistance
        t2 = round(float(high.iloc[-252:].max()), 2)
        if t2 <= t1:
            t2 = round(t1 + (t1 - entry), 2)

        return round(t1, 2), t2
    except Exception:
        risk = entry - stop
        return round(entry + risk * 2, 2), round(entry + risk * 3, 2)
