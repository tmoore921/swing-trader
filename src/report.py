"""Format analysis output as JSON and human-readable text."""

import json
from datetime import datetime


def build_json_output(
    mode: str,
    regime: dict,
    sectors: list[dict],
    candidates: list[dict],
    watchlist_tickers: list[str],
) -> dict:
    return {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "market_regime": regime,
        "leading_sectors": sectors,
        "candidates": candidates,
        "watchlist_tickers_to_evaluate": watchlist_tickers,
        "instructions_for_agent": _build_agent_instructions(regime, candidates),
    }


def _build_agent_instructions(regime: dict, candidates: list[dict]) -> dict:
    stance = regime.get("stance", "UNKNOWN")

    if stance in ("DEFENSIVE", "HALT"):
        return {
            "skip_orders": True,
            "reason": f"Market stance is {stance} — no new long entries",
        }

    orders = [c for c in candidates if c.get("agent_action") == "PLACE_ORDER"]
    watchlist_add = [c for c in candidates if c.get("agent_action") == "ADD_TO_WATCHLIST"]
    skip = [c for c in candidates if c.get("agent_action") == "SKIP"]

    return {
        "skip_orders": False,
        "place_orders": [
            {
                "ticker": c["ticker"],
                "limit_buy_price": c["risk"]["entry"],
                "stop_loss_price": c["risk"]["stop"],
                "take_profit_price": c["risk"]["t1"],
                "shares": c["risk"]["shares"],
                "order_type": "GFD_limit_buy",
                "note": "review_equity_order REQUIRED before place_equity_order",
            }
            for c in orders
            if c.get("risk") and c["risk"].get("valid")
        ],
        "add_to_watchlist": [c["ticker"] for c in watchlist_add],
        "skip": [{"ticker": c["ticker"], "reason": c.get("skip_reason", "")} for c in skip],
    }


def print_briefing(data: dict) -> None:
    """Print a human-readable summary to stdout."""
    regime = data["market_regime"]
    print(f"\n{'='*60}")
    print(f"SWING TRADER — {data['mode'].upper()} ANALYSIS")
    print(f"Generated: {data['generated_at'][:19]}")
    print(f"{'='*60}")
    print(f"\nMARKET STANCE: {regime['stance']}")
    print(f"VIX: {regime['vix']} | SPY vs 50SMA: {'above' if regime['spy']['above_sma50'] else 'below'} | QQQ vs 50SMA: {'above' if regime['qqq']['above_sma50'] else 'below'}")

    print(f"\nLEADING SECTORS:")
    for s in data.get("leading_sectors", []):
        print(f"  {s['ticker']} ({s['name']}): {s['return_pct']:+.1f}% | vs SPY: {s['vs_spy_pct']:+.1f}%")

    print(f"\nCANDIDATES ({len(data['candidates'])} screened):")
    for c in data["candidates"]:
        action = c.get("agent_action", "?")
        pattern = c.get("pattern", {})
        risk = c.get("risk", {})
        print(f"\n  {c['ticker']} [{action}]")
        print(f"    Pattern: {pattern.get('pattern', 'N/A')} | Pivot: ${pattern.get('pivot', 'N/A')} | Extended: {pattern.get('extended', False)}")
        if risk.get("valid"):
            print(f"    Entry: ${risk['entry']} | Stop: ${risk['stop']} | T1: ${risk.get('t1', 'N/A')} | Shares: {risk['shares']} | R:R: {risk.get('rr_t1', 'N/A')}")
        fund = c.get("fundamentals", {})
        print(f"    Fundamentals: {fund.get('quality', 'N/A')} | EPS: {fund.get('eps_growth_pct', 'N/A')}% | Rev: {fund.get('rev_growth_pct', 'N/A')}% | RS vs SPY: {fund.get('rs_vs_spy_6m', 'N/A')}%")

    instr = data.get("instructions_for_agent", {})
    if instr.get("skip_orders"):
        print(f"\n⚠ ORDERS SKIPPED: {instr['reason']}")
    else:
        orders = instr.get("place_orders", [])
        watchlist = instr.get("add_to_watchlist", [])
        print(f"\nORDERS TO PLACE: {len(orders)}")
        for o in orders:
            print(f"  BUY {o['shares']} shares {o['ticker']} limit @ ${o['limit_buy_price']} | Stop: ${o['stop_loss_price']} | TP: ${o['take_profit_price']}")
        print(f"WATCHLIST TO ADD: {', '.join(watchlist) if watchlist else 'none'}")

    print(f"\n{'='*60}\n")
