"""Shared per-ticker evaluation logic for both pre-market and EOD runs.

One data fetch per ticker, shared across Stage 2 / pattern / target math.
Fundamentals are NOT checked here — the agent verifies EPS/revenue/earnings via
web search before placing any order (Twelve Data free tier is price-only).
"""

from src.data_provider import get_history
from src.stage2 import check_stage2
from src.patterns import detect_pattern
from src.risk_engine import calculate_position, estimate_targets
from config import BUY_SIGNAL_THRESHOLD_PCT


def evaluate_ticker(ticker: str, from_watchlist: bool = False) -> dict:
    """Run the full price-based evaluation for one ticker."""
    hist = get_history(ticker, outputsize=500)

    if hist is None:
        return {
            "ticker": ticker,
            "from_watchlist": from_watchlist,
            "agent_action": "VERIFY_VIA_WEBSEARCH",
            "skip_reason": "No price data from provider — agent should evaluate via web search",
        }

    stage2 = check_stage2(ticker, df=hist)
    if not stage2["passes"]:
        return {
            "ticker": ticker,
            "from_watchlist": from_watchlist,
            "stage2": stage2,
            "agent_action": "SKIP",
            "skip_reason": f"Stage 2 failed: {stage2.get('failed_conditions') or stage2.get('reason')}",
        }

    pattern = detect_pattern(ticker, df=hist)
    entry = pattern.get("pivot")
    risk = {}
    action = "SKIP"
    skip_reason = ""

    if entry:
        stop = stage2.get("sma50") or (entry * 0.92)  # fallback: 8% below entry
        t1, t2 = estimate_targets(ticker, entry, stop, df=hist)
        risk = calculate_position(entry=entry, stop=stop, t1=t1, t2=t2)

        price = stage2["price"]
        pct_from_pivot = (price / entry - 1)

        if pattern.get("extended"):
            action = "ADD_TO_WATCHLIST"
            skip_reason = "Extended >5% above pivot — do not chase"
        elif 0 <= pct_from_pivot <= BUY_SIGNAL_THRESHOLD_PCT:
            if risk.get("meets_min_rr"):
                action = "PLACE_ORDER"
            else:
                action = "ADD_TO_WATCHLIST"
                skip_reason = f"At pivot but R:R {risk.get('rr_t1')} < 2.0"
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
        "risk": risk,
        "agent_action": action,
        "skip_reason": skip_reason,
        "fundamentals_unverified": True,
    }
