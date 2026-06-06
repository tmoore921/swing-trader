#!/usr/bin/env python3
"""
End-of-day analysis entry point (~3:30 PM ET).

Watchlist-first, same as the pre-market run: the agent supplies watchlist names
plus fresh web-search finds; this script runs the price-based math and emits JSON
trade plans for the agent to execute via Robinhood MCP.

Usage:
    export TWELVEDATA_API_KEY=...
    uv run python run_eod.py \
        --watchlist AAPL,MSFT \
        --new NVDA,AVGO,CRWD \
        --output /tmp/swing_eod.json
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.market_regime import check_market_regime
from src.evaluate import evaluate_ticker
from src.report import build_json_output, print_briefing


def _parse_tickers(raw: str) -> list[str]:
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default="", help="Tickers from the Robinhood watchlist")
    parser.add_argument("--new", default="", help="Fresh tickers from agent web search")
    parser.add_argument("--output", default="/tmp/swing_eod.json")
    args = parser.parse_args()

    watchlist = _parse_tickers(args.watchlist)
    new_scan = _parse_tickers(args.new)

    print("Checking market regime...")
    regime = check_market_regime()
    print(f"  Stance: {regime['stance']} | VIX: {regime.get('vix')}")

    if regime["stance"] in ("DEFENSIVE", "HALT"):
        data = build_json_output("eod", regime, [], watchlist, new_scan)
        _write_and_print(data, args.output)
        return

    candidates = []
    seen = set()
    for ticker in watchlist:
        if ticker in seen:
            continue
        seen.add(ticker)
        print(f"  [watchlist] {ticker}...")
        candidates.append(evaluate_ticker(ticker, from_watchlist=True))

    for ticker in new_scan:
        if ticker in seen:
            continue
        seen.add(ticker)
        print(f"  [new] {ticker}...")
        candidates.append(evaluate_ticker(ticker, from_watchlist=False))

    data = build_json_output("eod", regime, candidates, watchlist, new_scan)
    _write_and_print(data, args.output)


def _write_and_print(data: dict, output_path: str):
    print_briefing(data)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"JSON output written to: {output_path}")


if __name__ == "__main__":
    main()
