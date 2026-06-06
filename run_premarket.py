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
        --cash 480.50 \
        --output /tmp/swing_premarket.json

--watchlist     : tickers already on the Robinhood "Swing Candidates" watchlist
--new           : fresh tickers the agent found via web search (used to broaden)
--cash          : Robinhood buying power (agent passes from get_accounts) so sizing
                  and the portfolio cash cap reflect reality. Optional.
--existing-risk : open dollar-risk already in the book (sum of (entry-stop)*shares
                  over current positions) so new orders respect the 6% heat cap.
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
    parser.add_argument("--output", default="/tmp/swing_premarket.json")
    args = parser.parse_args()

    run_analysis(
        mode="premarket",
        watchlist=parse_tickers(args.watchlist),
        new_scan=parse_tickers(args.new),
        output_path=args.output,
        cash_available=args.cash,
        existing_risk=args.existing_risk,
    )


if __name__ == "__main__":
    main()
