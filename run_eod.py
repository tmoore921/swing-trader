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
        --cash 480.50 \
        --output /tmp/swing_eod.json

See run_premarket.py for the --cash / --existing-risk account-state flags.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline import run_analysis, parse_tickers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watchlist", default="", help="Tickers from the Robinhood watchlist")
    parser.add_argument("--new", default="", help="Fresh tickers from agent web search")
    parser.add_argument("--cash", type=float, default=None, help="Available buying power")
    parser.add_argument("--existing-risk", type=float, default=0.0, help="Open dollar-risk in book")
    parser.add_argument("--output", default="/tmp/swing_eod.json")
    args = parser.parse_args()

    run_analysis(
        mode="eod",
        watchlist=parse_tickers(args.watchlist),
        new_scan=parse_tickers(args.new),
        output_path=args.output,
        cash_available=args.cash,
        existing_risk=args.existing_risk,
    )


if __name__ == "__main__":
    main()
