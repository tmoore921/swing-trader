"""Shared analysis pipeline for the pre-market and EOD entry points.

The two run scripts were near-identical; the only real differences (framing,
order time-in-force) live in the routine prompts, not here. This module is the
single source of truth for the run sequence:

  regime → per-ticker evaluate (RS-aware) → RS ranking → portfolio heat cap →
  JSON output → journal.

Optional account state (--cash, --existing-risk) lets the routine agent feed real
Robinhood buying power / open risk in so sizing and heat caps reflect reality.
"""

import json
from pathlib import Path

from src.market_regime import regime_and_benchmark
from src.evaluate import evaluate_ticker
from src.rs import rank_candidates
from src.portfolio import apply_portfolio_limits
from src.report import build_json_output, print_briefing
from src.journal import record_run


def parse_tickers(raw: str) -> list[str]:
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def run_analysis(
    mode: str,
    watchlist: list[str],
    new_scan: list[str],
    output_path: str,
    cash_available: float | None = None,
    existing_risk: float = 0.0,
) -> dict:
    print("Checking market regime...")
    regime, spy_df = regime_and_benchmark()
    print(f"  Stance: {regime['stance']} | VIX: {regime.get('vix')}"
          f"{' | DATA FAILURE' if regime.get('data_failure') else ''}")

    if regime["stance"] in ("DEFENSIVE", "HALT"):
        data = build_json_output(mode, regime, [], watchlist, new_scan)
        record_run(mode, regime, [])
        return _write_and_print(data, output_path)

    # Watchlist-first: evaluate carryover names, then broaden with new finds.
    candidates = []
    seen = set()
    for ticker in watchlist:
        if ticker in seen:
            continue
        seen.add(ticker)
        print(f"  [watchlist] {ticker}...")
        candidates.append(
            evaluate_ticker(ticker, from_watchlist=True, spy_df=spy_df, cash_available=cash_available)
        )

    for ticker in new_scan:
        if ticker in seen:
            continue
        seen.add(ticker)
        print(f"  [new] {ticker}...")
        candidates.append(
            evaluate_ticker(ticker, from_watchlist=False, spy_df=spy_df, cash_available=cash_available)
        )

    # Rank by relative strength, then enforce portfolio-level heat / cash limits.
    rank_candidates(candidates)
    heat = apply_portfolio_limits(
        candidates, cash_available=cash_available, existing_risk=existing_risk
    )
    print(f"  Portfolio: kept {heat['orders_kept']} | demoted {heat['orders_demoted']} "
          f"| new risk ${heat['new_risk_committed']} of ${heat['max_portfolio_risk']}")

    data = build_json_output(mode, regime, candidates, watchlist, new_scan)
    data["portfolio"] = heat
    record_run(mode, regime, candidates)
    return _write_and_print(data, output_path)


def _write_and_print(data: dict, output_path: str) -> dict:
    print_briefing(data)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"JSON output written to: {output_path}")
    return data
