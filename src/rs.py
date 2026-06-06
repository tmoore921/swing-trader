"""Relative strength vs a benchmark (SPY).

Minervini's edge is concentrating in the *strongest* names, not merely names in
an uptrend. We score each candidate by its trailing return minus SPY's over
several horizons, weighted, then rank. Higher score = stronger leadership.
"""

import pandas as pd
from config import RS_HORIZONS


def _trailing_return(close: pd.Series, lookback: int) -> float | None:
    if close is None or len(close) <= lookback:
        return None
    past = float(close.iloc[-(lookback + 1)])
    now = float(close.iloc[-1])
    if past <= 0:
        return None
    return now / past - 1.0


def compute_rs(ticker_df: pd.DataFrame | None, spy_df: pd.DataFrame | None) -> dict:
    """Weighted relative-strength score vs SPY across RS_HORIZONS.

    Returns {"rs_score": float|None, "by_horizon": {...}}. Score is in percentage
    points of cumulative out/under-performance; None if data is too short or SPY
    is missing.
    """
    if ticker_df is None or spy_df is None:
        return {"rs_score": None, "by_horizon": {}}

    tclose = ticker_df["Close"].astype(float)
    sclose = spy_df["Close"].astype(float)

    by_horizon: dict[str, float] = {}
    weighted_sum = 0.0
    weight_used = 0.0
    for lookback, weight in RS_HORIZONS.items():
        t_ret = _trailing_return(tclose, lookback)
        s_ret = _trailing_return(sclose, lookback)
        if t_ret is None or s_ret is None:
            continue
        rel = (t_ret - s_ret) * 100.0
        by_horizon[f"{lookback}d"] = round(rel, 2)
        weighted_sum += weight * rel
        weight_used += weight

    if weight_used == 0:
        return {"rs_score": None, "by_horizon": {}}

    # Normalize by the weight actually used so partial-history names aren't penalized.
    return {"rs_score": round(weighted_sum / weight_used, 2), "by_horizon": by_horizon}


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Assign rs_rank (1 = strongest) among candidates that have an rs_score.

    Mutates and returns the list. Candidates without a score get rs_rank=None.
    """
    scored = [c for c in candidates if (c.get("rs") or {}).get("rs_score") is not None]
    scored.sort(key=lambda c: c["rs"]["rs_score"], reverse=True)
    for rank, c in enumerate(scored, start=1):
        c["rs"]["rs_rank"] = rank
        c["rs"]["rs_universe"] = len(scored)
    for c in candidates:
        if (c.get("rs") or {}).get("rs_score") is None and c.get("rs") is not None:
            c["rs"]["rs_rank"] = None
    return candidates
