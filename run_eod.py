#!/usr/bin/env python3
"""
End-of-day analysis entry point (~3:30 PM ET).

Usage:
    uv run python run_eod.py [--watchlist AAPL,MSFT,AMD] [--output /tmp/eod_analysis.json]

Runs a full evaluation of today's market and top momentum stocks.
Outputs JSON for the CCR agent to act on via Robinhood MCP.
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.market_regime import check_market_regime
from src.sector_scanner import get_leading_sectors
from src.screener import screen_stocks
from src.stage2 import check_stage2
from src.fundamentals import check_fundamentals
from src.patterns import detect_pattern
from src.risk_engine import calculate_position, estimate_targets
from src.report import build_json_output, print_briefing
from config import BUY_SIGNAL_THRESHOLD_PCT, SCREENER_TOP_CANDIDATES


def evaluate_candidate(ticker: str) -> dict:
    stage2 = check_stage2(ticker)
    if not stage2["passes"]:
        return {
            "ticker": ticker,
            "stage2": stage2,
            "agent_action": "SKIP",
            "skip_reason": f"Stage 2 failed: {stage2.get('failed_conditions', [])}",
        }

    fundamentals = check_fundamentals(ticker)
    if fundamentals.get("disqualified"):
        return {
            "ticker": ticker,
            "stage2": stage2,
            "fundamentals": fundamentals,
            "agent_action": "SKIP",
            "skip_reason": "Fundamentals disqualified (2+ FAIL)",
        }

    pattern = detect_pattern(ticker)
    entry = pattern.get("pivot")
    risk = {}
    action = "SKIP"

    if entry:
        stop = stage2.get("sma50") or (entry * 0.92)
        t1, t2 = estimate_targets(ticker, entry, stop)
        risk = calculate_position(entry=entry, stop=stop, t1=t1, t2=t2)
        price = stage2["price"]
        pct_from_pivot = (price / entry - 1)

        if pattern.get("extended"):
            action = "ADD_TO_WATCHLIST"
        elif 0 <= pct_from_pivot <= BUY_SIGNAL_THRESHOLD_PCT:
            action = "PLACE_ORDER" if risk.get("meets_min_rr") else "ADD_TO_WATCHLIST"
        elif -0.05 <= pct_from_pivot < 0:
            # Within 5% below pivot — approaching, add to watchlist
            action = "ADD_TO_WATCHLIST"
        elif pattern["pattern"] not in ("NO SETUP", "ERROR", "INSUFFICIENT_DATA"):
            action = "ADD_TO_WATCHLIST"
    else:
        action = "ADD_TO_WATCHLIST" if pattern["pattern"] not in ("NO SETUP", "ERROR") else "SKIP"

    return {
        "ticker": ticker,
        "stage2": stage2,
        "fundamentals": fundamentals,
        "pattern": pattern,
        "risk": risk,
        "agent_action": action,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default="", help="Comma-separated tickers from Robinhood watchlist")
    parser.add_argument("--output", default="/tmp/swing_eod.json", help="Path to write JSON output")
    args = parser.parse_args()

    watchlist_tickers = [t.strip().upper() for t in args.watchlist.split(",") if t.strip()]

    print("Checking market regime...")
    regime = check_market_regime()
    print(f"  Stance: {regime['stance']} | VIX: {regime['vix']}")

    if regime["stance"] in ("DEFENSIVE", "HALT"):
        data = build_json_output("eod", regime, [], [], watchlist_tickers)
        _write_and_print(data, args.output)
        return

    print("Scanning leading sectors...")
    sectors = get_leading_sectors()

    print("Screening stock universe (this takes ~60s)...")
    screened = screen_stocks()
    top_tickers = [s["ticker"] for s in screened[:SCREENER_TOP_CANDIDATES]]
    print(f"  Top candidates: {', '.join(top_tickers)}")

    print("Running full evaluation...")
    candidates = []
    for ticker in top_tickers:
        print(f"  {ticker}...")
        result = evaluate_candidate(ticker)
        candidates.append(result)

    data = build_json_output("eod", regime, sectors, candidates, watchlist_tickers)
    _write_and_print(data, args.output)


def _write_and_print(data: dict, output_path: str):
    print_briefing(data)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"JSON output written to: {output_path}")


if __name__ == "__main__":
    main()
