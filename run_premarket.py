#!/usr/bin/env python3
"""
Pre-market analysis entry point (~8:30 AM ET).

Watchlist-first: the agent supplies tickers it gathered (watchlist names first,
broadened with web-search momentum names when the watchlist is thin/empty).
This script runs the price-based math on those tickers and emits JSON.

Usage:
    export TWELVEDATA_API_KEY=...
    uv run python run_premarket.py \
        --watchlist AAPL,MSFT \
        --new NVDA,AVGO,CRWD \
        --output /tmp/swing_premarket.json

--watchlist : tickers already on the Robinhood "Swing Candidates" watchlist
--new       : fresh tickers the agent found via web search (used to broaden,
              especially when the watchlist is empty)
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
    parser.add_argument("--output", default="/tmp/swing_premarket.json")
    args = parser.parse_args()

    watchlist = _parse_tickers(args.watchlist)
    new_scan = _parse_tickers(args.new)

    print("Checking market regime...")
    regime = check_market_regime()
    print(f"  Stance: {regime['stance']} | VIX: {regime.get('vix')}")

    if regime["stance"] in ("DEFENSIVE", "HALT"):
        data = build_json_output("premarket", regime, [], watchlist, new_scan)
        _write_and_print(data, args.output)
        return

    # Watchlist-first: evaluate carryover names, then broaden with new finds.
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

    data = build_json_output("premarket", regime, candidates, watchlist, new_scan)
    _write_and_print(data, args.output)


def _write_and_print(data: dict, output_path: str):
    print_briefing(data)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"JSON output written to: {output_path}")


if __name__ == "__main__":
    main()
