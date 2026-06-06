"""Portfolio-level risk enforcement across a batch of candidates.

Per-ticker sizing caps a *single* trade, but nothing stops the system from
emitting six 1%-risk orders at once (6% heat) or orders whose combined notional
exceeds available cash. This module is the missing aggregate gate: it keeps the
strongest orders and demotes the rest to the watchlist once a limit is hit.
"""

from config import ACCOUNT_SIZE, MAX_PORTFOLIO_RISK_PCT


def _order_priority(c: dict) -> tuple:
    """Sort key: strongest first. RS rank ascending (1 best), then R:R descending."""
    rs = c.get("rs") or {}
    rank = rs.get("rs_rank")
    rank_key = rank if rank is not None else 10_000
    rr = (c.get("risk") or {}).get("rr_t1") or 0.0
    return (rank_key, -rr)


def apply_portfolio_limits(
    candidates: list[dict],
    account_size: float = ACCOUNT_SIZE,
    cash_available: float | None = None,
    existing_risk: float = 0.0,
) -> dict:
    """Demote PLACE_ORDER candidates that would breach portfolio heat or cash.

    `existing_risk` is the open dollar-risk already in the book (from current
    positions) so new orders are added on top of it. Mutates candidates in place
    (changes agent_action / appends skip_reason) and returns a summary dict.
    """
    max_risk = account_size * MAX_PORTFOLIO_RISK_PCT
    orders = [c for c in candidates if c.get("agent_action") == "PLACE_ORDER"]
    orders.sort(key=_order_priority)

    risk_budget_left = max_risk - existing_risk
    cash_left = cash_available
    kept, demoted = [], []

    for c in orders:
        risk = c.get("risk") or {}
        d_risk = risk.get("dollar_risk") or 0.0
        notional = risk.get("position_size") or 0.0

        breaches_heat = d_risk > risk_budget_left + 1e-9
        breaches_cash = cash_left is not None and notional > cash_left + 1e-9

        if breaches_heat or breaches_cash:
            reason = (
                "portfolio heat cap reached" if breaches_heat else "insufficient cash for combined orders"
            )
            c["agent_action"] = "ADD_TO_WATCHLIST"
            prev = c.get("skip_reason") or ""
            c["skip_reason"] = f"{reason}{' | ' + prev if prev else ''}"
            demoted.append(c["ticker"])
            continue

        risk_budget_left -= d_risk
        if cash_left is not None:
            cash_left -= notional
        kept.append(c["ticker"])

    return {
        "max_portfolio_risk": round(max_risk, 2),
        "existing_risk": round(existing_risk, 2),
        "new_risk_committed": round(max_risk - existing_risk - risk_budget_left, 2),
        "orders_kept": kept,
        "orders_demoted": demoted,
        "cash_remaining": round(cash_left, 2) if cash_left is not None else None,
    }
