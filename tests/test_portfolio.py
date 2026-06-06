"""Tests for portfolio-level heat and cash enforcement."""

from src.portfolio import apply_portfolio_limits
from config import MAX_PORTFOLIO_RISK_PCT


def _order(ticker, dollar_risk, notional, rs_rank=None, rr=3.0):
    return {
        "ticker": ticker,
        "agent_action": "PLACE_ORDER",
        "rs": {"rs_rank": rs_rank},
        "risk": {"dollar_risk": dollar_risk, "position_size": notional, "rr_t1": rr},
    }


def test_heat_cap_demotes_excess_orders():
    # $500 account -> 6% = $30 risk budget. Three $20-risk orders = $60 > cap.
    cands = [
        _order("A", 20, 100, rs_rank=1),
        _order("B", 20, 100, rs_rank=2),
        _order("C", 20, 100, rs_rank=3),
    ]
    summary = apply_portfolio_limits(cands, account_size=500)
    actions = {c["ticker"]: c["agent_action"] for c in cands}
    # Strongest (A) kept; once budget exhausted the rest demote.
    assert actions["A"] == "PLACE_ORDER"
    assert "A" in summary["orders_kept"]
    assert summary["new_risk_committed"] <= 500 * MAX_PORTFOLIO_RISK_PCT + 1e-9
    assert len(summary["orders_demoted"]) >= 1
    for t in summary["orders_demoted"]:
        assert actions[t] == "ADD_TO_WATCHLIST"


def test_strongest_rs_kept_first():
    cands = [
        _order("WEAK", 25, 100, rs_rank=5),
        _order("STRONG", 25, 100, rs_rank=1),
    ]
    apply_portfolio_limits(cands, account_size=500)  # budget $30, only one fits
    actions = {c["ticker"]: c["agent_action"] for c in cands}
    assert actions["STRONG"] == "PLACE_ORDER"
    assert actions["WEAK"] == "ADD_TO_WATCHLIST"


def test_cash_cap_demotes():
    # Plenty of risk budget but only $120 cash; two $100 notional orders.
    cands = [_order("A", 5, 100, rs_rank=1), _order("B", 5, 100, rs_rank=2)]
    summary = apply_portfolio_limits(cands, account_size=5000, cash_available=120)
    actions = {c["ticker"]: c["agent_action"] for c in cands}
    assert actions["A"] == "PLACE_ORDER"
    assert actions["B"] == "ADD_TO_WATCHLIST"
    assert "insufficient cash" in cands[1]["skip_reason"]


def test_existing_risk_reduces_budget():
    # $28 already at risk, $30 cap -> only $2 left, a $20 order can't fit.
    cands = [_order("A", 20, 100, rs_rank=1)]
    apply_portfolio_limits(cands, account_size=500, existing_risk=28)
    assert cands[0]["agent_action"] == "ADD_TO_WATCHLIST"
