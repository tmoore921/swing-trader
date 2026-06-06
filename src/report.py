"""Format analysis output as JSON and human-readable text."""

from datetime import datetime


def build_json_output(
    mode: str,
    regime: dict,
    candidates: list[dict],
    watchlist_tickers: list[str],
    new_scan_tickers: list[str],
) -> dict:
    return {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "market_regime": regime,
        "candidates": candidates,
        "watchlist_tickers_evaluated": watchlist_tickers,
        "new_scan_tickers_evaluated": new_scan_tickers,
        "instructions_for_agent": _build_agent_instructions(regime, candidates),
    }


def _is_defensive(regime: dict) -> bool:
    return regime.get("stance") in ("DEFENSIVE", "HALT")


def _build_agent_instructions(regime: dict, candidates: list[dict]) -> dict:
    if _is_defensive(regime):
        return {
            "skip_orders": True,
            "reason": f"Market stance is {regime.get('stance')} — no new long entries",
        }

    orders = [c for c in candidates if c.get("agent_action") == "PLACE_ORDER"]
    watchlist_add = [c for c in candidates if c.get("agent_action") == "ADD_TO_WATCHLIST"]
    skip = [c for c in candidates if c.get("agent_action") == "SKIP"]
    no_data = [c for c in candidates if c.get("agent_action") == "VERIFY_VIA_WEBSEARCH"]

    return {
        "skip_orders": False,
        "verify_fundamentals_before_ordering": True,
        "place_orders": [
            {
                "ticker": c["ticker"],
                "from_watchlist": c.get("from_watchlist", False),
                "limit_buy_price": c["risk"]["entry"],
                "stop_loss_price": c["risk"]["stop"],
                "take_profit_price": c["risk"]["t1"],
                "shares": c["risk"]["shares"],
                "rr_t1": c["risk"].get("rr_t1"),
                "order_type": "limit_buy",
                "note": "Verify fundamentals + earnings via web search, then review_equity_order BEFORE place_equity_order",
            }
            for c in orders
            if c.get("risk") and c["risk"].get("valid")
        ],
        "add_to_watchlist": [c["ticker"] for c in watchlist_add],
        "skip": [{"ticker": c["ticker"], "reason": c.get("skip_reason", "")} for c in skip],
        "verify_via_websearch": [c["ticker"] for c in no_data],
    }


def print_briefing(data: dict) -> None:
    regime = data["market_regime"]
    spy = regime.get("spy") or {}
    qqq = regime.get("qqq") or {}
    print(f"\n{'='*60}")
    print(f"SWING TRADER — {data['mode'].upper()} ANALYSIS")
    print(f"Generated: {data['generated_at'][:19]}")
    print(f"{'='*60}")
    print(f"\nMARKET STANCE: {regime['stance']}")
    print(f"VIX: {regime.get('vix', 'N/A')} | conditions met: {regime.get('conditions_met')}/6")
    print(f"SPY vs 50SMA: {'above' if spy.get('above_sma50') else 'below/NA'} | "
          f"QQQ vs 50SMA: {'above' if qqq.get('above_sma50') else 'below/NA'}")
    for note in regime.get("notes", []):
        print(f"  ⚠ {note}")

    print(f"\nCANDIDATES ({len(data['candidates'])} evaluated):")
    for c in data["candidates"]:
        action = c.get("agent_action", "?")
        src = "watchlist" if c.get("from_watchlist") else "new"
        pattern = c.get("pattern", {})
        risk = c.get("risk", {})
        print(f"\n  {c['ticker']} [{action}] ({src})")
        print(f"    Pattern: {pattern.get('pattern', 'N/A')} | Pivot: ${pattern.get('pivot', 'N/A')} | Extended: {pattern.get('extended', False)}")
        if risk.get("valid"):
            print(f"    Entry: ${risk['entry']} | Stop: ${risk['stop']} | T1: ${risk.get('t1', 'N/A')} | Shares: {risk['shares']} | R:R: {risk.get('rr_t1', 'N/A')}")
        if c.get("skip_reason"):
            print(f"    Skip: {c['skip_reason']}")

    instr = data.get("instructions_for_agent", {})
    if instr.get("skip_orders"):
        print(f"\n⚠ ORDERS SKIPPED: {instr['reason']}")
    else:
        orders = instr.get("place_orders", [])
        watchlist = instr.get("add_to_watchlist", [])
        print(f"\nORDERS TO PLACE (after agent verifies fundamentals): {len(orders)}")
        for o in orders:
            tag = "watchlist" if o.get("from_watchlist") else "new"
            print(f"  BUY {o['shares']} {o['ticker']} limit @ ${o['limit_buy_price']} | Stop: ${o['stop_loss_price']} | TP: ${o['take_profit_price']} ({tag})")
        print(f"WATCHLIST TO ADD: {', '.join(watchlist) if watchlist else 'none'}")

    print(f"\n{'='*60}\n")
