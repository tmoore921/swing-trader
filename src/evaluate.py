"""Shared per-ticker evaluation logic for both pre-market and EOD runs.

One data fetch per ticker, shared across Stage 2 / pattern / target math.
Fundamentals are NOT checked here — the agent verifies EPS/revenue/earnings via
web search before placing any order (Twelve Data free tier is price-only).
"""

import pandas as pd

from src.data_provider import get_history
from src.stage2 import check_stage2
from src.patterns import detect_pattern
from src.risk_engine import calculate_position, estimate_targets, atr_stop
from src.rs import compute_rs
from config import BUY_SIGNAL_THRESHOLD_PCT, MIN_PRICE, MIN_AVG_DOLLAR_VOLUME


def _avg_dollar_volume(hist: pd.DataFrame, days: int = 20) -> float:
    seg = hist.iloc[-days:]
    return float((seg["Close"].astype(float) * seg["Volume"].astype(float)).mean())


def evaluate_ticker(
    ticker: str,
    from_watchlist: bool = False,
    spy_df: pd.DataFrame | None = None,
    cash_available: float | None = None,
) -> dict:
    """Run the full price-based evaluation for one ticker."""
    hist = get_history(ticker, outputsize=500)

    if hist is None:
        return {
            "ticker": ticker,
            "from_watchlist": from_watchlist,
            "agent_action": "VERIFY_VIA_WEBSEARCH",
            "skip_reason": "No price data from provider — agent should evaluate via web search",
        }

    # Relative strength vs SPY (used for ranking and gating later).
    rs = compute_rs(hist, spy_df)

    # Liquidity floor — a small account can't exit thin names cleanly.
    price_now = float(hist["Close"].iloc[-1])
    adv = _avg_dollar_volume(hist)
    if price_now < MIN_PRICE or adv < MIN_AVG_DOLLAR_VOLUME:
        return {
            "ticker": ticker,
            "from_watchlist": from_watchlist,
            "rs": rs,
            "agent_action": "SKIP",
            "skip_reason": (
                f"Illiquid/low-price: ${price_now:.2f} price, "
                f"${adv/1e6:.1f}M avg $vol (floors ${MIN_PRICE}, ${MIN_AVG_DOLLAR_VOLUME/1e6:.0f}M)"
            ),
        }

    stage2 = check_stage2(ticker, df=hist)
    if not stage2["passes"]:
        return {
            "ticker": ticker,
            "from_watchlist": from_watchlist,
            "stage2": stage2,
            "rs": rs,
            "agent_action": "SKIP",
            "skip_reason": f"Stage 2 failed: {stage2.get('failed_conditions') or stage2.get('reason')}",
        }

    pattern = detect_pattern(ticker, df=hist)
    entry = pattern.get("pivot")
    risk = {}
    action = "SKIP"
    skip_reason = ""

    if entry:
        # Structural stop (SMA50, fallback 8%) widened to at least an ATR-based
        # distance so a stop hugging the entry can't oversize the position or get
        # whipsawed out. min() picks the lower (wider) stop.
        sma50 = stage2.get("sma50")
        structural = sma50 if (sma50 and sma50 < entry) else entry * 0.92
        a_stop = atr_stop(entry, hist)
        stop = min(structural, a_stop) if a_stop else structural

        t1, t2 = estimate_targets(ticker, entry, stop, df=hist)
        risk = calculate_position(
            entry=entry, stop=stop, t1=t1, t2=t2, cash_available=cash_available
        )

        price = stage2["price"]
        pct_from_pivot = (price / entry - 1)

        # Quality gates that must hold to actually PLACE an order (vs watchlist).
        volume_ok = bool(pattern.get("volume_confirmation"))
        near_high = bool(stage2.get("within_25pct_of_52w_high"))

        if not risk.get("valid"):
            action = "SKIP"
            skip_reason = f"Position invalid: {risk.get('reason')}"
        elif pattern.get("extended"):
            action = "ADD_TO_WATCHLIST"
            skip_reason = "Extended >5% above pivot — do not chase"
        elif 0 <= pct_from_pivot <= BUY_SIGNAL_THRESHOLD_PCT:
            gate_fail = []
            if not risk.get("meets_min_rr"):
                gate_fail.append(f"R:R {risk.get('rr_t1')} < 2.0")
            if not volume_ok:
                gate_fail.append("no volume confirmation")
            if not near_high:
                gate_fail.append("not within 25% of 52w high")
            if gate_fail:
                action = "ADD_TO_WATCHLIST"
                skip_reason = "At pivot but " + "; ".join(gate_fail)
            else:
                action = "PLACE_ORDER"
        elif -0.05 <= pct_from_pivot < 0:
            action = "ADD_TO_WATCHLIST"
            skip_reason = "Approaching pivot (within 5% below)"
        elif pattern["pattern"] not in ("NO SETUP", "DATA_UNAVAILABLE", "INSUFFICIENT_DATA", "ERROR"):
            action = "ADD_TO_WATCHLIST"
            skip_reason = "Valid pattern, still building base"
        else:
            action = "SKIP"
            skip_reason = "No actionable pattern"
    else:
        if pattern["pattern"] not in ("NO SETUP", "DATA_UNAVAILABLE", "INSUFFICIENT_DATA", "ERROR"):
            action = "ADD_TO_WATCHLIST"
        else:
            action = "SKIP"
            skip_reason = pattern.get("note", "No setup detected")

    return {
        "ticker": ticker,
        "from_watchlist": from_watchlist,
        "stage2": stage2,
        "pattern": pattern,
        "rs": rs,
        "risk": risk,
        "agent_action": action,
        "skip_reason": skip_reason,
        "fundamentals_unverified": True,
    }
