"""Position sizing and R:R calculations."""

import pandas as pd
from config import (
    ACCOUNT_SIZE,
    RISK_PER_TRADE,
    MIN_RR,
    PREFERRED_RR,
    MAX_POSITION_PCT,
    ATR_PERIOD,
    ATR_STOP_MULTIPLIER,
)
from src.data_provider import get_history


def calculate_position(
    entry: float,
    stop: float,
    t1: float | None = None,
    t2: float | None = None,
    account_size: float = ACCOUNT_SIZE,
    cash_available: float | None = None,
) -> dict:
    """Return full position sizing and R:R data.

    Shares are sized off the fixed dollar-risk budget, then **clamped** so the
    notional never exceeds the lesser of MAX_POSITION_PCT of the account or the
    cash actually available. A tight stop can otherwise demand more shares than
    the whole account holds (e.g. a $0.50 stop distance → 10 shares → 200% of a
    $500 account). After clamping, dollar-risk is recomputed from the real share
    count, so a clamped trade simply risks *less* than the nominal budget.
    """
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        return {"valid": False, "reason": "stop_at_or_above_entry"}
    if entry <= 0:
        return {"valid": False, "reason": "invalid_entry"}

    risk_based_shares = RISK_PER_TRADE / risk_per_share

    # Caps
    max_shares_by_pct = (account_size * MAX_POSITION_PCT) / entry
    cap_reasons = {"max_position_pct": max_shares_by_pct}
    if cash_available is not None:
        cap_reasons["cash_available"] = cash_available / entry

    binding_cap = min(cap_reasons.values())
    shares = min(risk_based_shares, binding_cap)
    clamped = shares < risk_based_shares - 1e-9

    # If even a minimal position can't be afforded, the trade isn't placeable.
    if shares <= 0 or shares * entry < 1.0:
        return {
            "valid": False,
            "reason": "insufficient_capital_for_min_position",
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "cash_available": cash_available,
        }

    position_size = shares * entry
    position_pct = position_size / account_size * 100
    dollar_risk = shares * risk_per_share

    rr_t1 = round((t1 - entry) / risk_per_share, 2) if t1 and t1 > entry else None
    rr_t2 = round((t2 - entry) / risk_per_share, 2) if t2 and t2 > entry else None

    return {
        "valid": True,
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "risk_per_share": round(risk_per_share, 2),
        "dollar_risk": round(dollar_risk, 2),
        "nominal_dollar_risk": round(RISK_PER_TRADE, 2),
        "clamped": clamped,
        "clamp_reason": (
            min(cap_reasons, key=cap_reasons.get) if clamped else None
        ),
        "shares": round(shares, 4),
        "position_size": round(position_size, 2),
        "position_pct_of_account": round(position_pct, 1),
        "t1": round(t1, 2) if t1 else None,
        "t2": round(t2, 2) if t2 else None,
        "rr_t1": rr_t1,
        "rr_t2": rr_t2,
        "meets_min_rr": bool(rr_t1 and rr_t1 >= MIN_RR),
        "meets_preferred_rr": bool(rr_t1 and rr_t1 >= PREFERRED_RR),
        # Should never trip now that shares are clamped, but kept as a guard rail.
        "oversized_warning": position_pct > MAX_POSITION_PCT * 100 + 1e-6,
    }


def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float | None:
    """Wilder's Average True Range over `period` bars. None if insufficient data."""
    if df is None or len(df) < period + 1:
        return None
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    # Wilder smoothing via EWM(alpha=1/period)
    atr_series = true_range.ewm(alpha=1 / period, adjust=False).mean()
    val = float(atr_series.iloc[-1])
    return round(val, 4) if val > 0 else None


def atr_stop(entry: float, df: pd.DataFrame, multiplier: float = ATR_STOP_MULTIPLIER) -> float | None:
    """Stop placed `multiplier` ATRs below entry. None if ATR unavailable."""
    a = atr(df)
    if a is None:
        return None
    stop = entry - multiplier * a
    return round(stop, 2) if stop > 0 else None


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
