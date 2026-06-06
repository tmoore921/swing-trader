# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A swing-trading analysis engine that runs as the Python half of a two-tier automated trading system. It is driven by two scheduled Claude Code "routines" (remote CCR agents) that fire pre-market (~8:30 AM ET) and end-of-day (~3:30 PM ET), Mon–Fri, against a small (~$500) Robinhood account.

**Critical:** this repo is only one half of the system. The other half — ticker discovery, fundamental verification, VIX lookup, position/exit management, and all order/watchlist execution — runs as **scheduled routine prompts on claude.ai** (the repo never contains or calls Robinhood/order code). Those prompts are now version-controlled here under **`prompts/`** (`premarket_routine.md`, `eod_routine.md`, plus a deploy README) so they're diffable — the live claude.ai routines are the deployed copies and must be kept in sync. Changing strategy behavior often means editing **both** the Python here **and** the two prompt files (then re-pasting them into the routine UI).

## Commands

```bash
uv sync                                          # install deps (uses uv, creates .venv with Python 3.11+)

# Run analysis — the API key MUST be passed inline (see "Why inline" below)
TWELVEDATA_API_KEY=<key> uv run python run_premarket.py --watchlist AAPL,MSFT --new NVDA,AVGO --cash 480 --output /tmp/swing_premarket.json
TWELVEDATA_API_KEY=<key> uv run python run_eod.py       --watchlist AAPL,MSFT --new NVDA,AVGO --cash 480 --output /tmp/swing_eod.json

# Data-layer diagnostic — prints "OK — SPY returned N rows" or "FAILED — <raw API reason>"
TWELVEDATA_API_KEY=<key> uv run python -m src.data_provider SPY

# Email a report (Resend) — prints "OK — email sent ..." or "FAILED — <reason>"
RESEND_API_KEY=<key> uv run python send_report.py --subject "..." --to you@example.com --body-file /tmp/briefing.txt

# Tests (pytest, network-free — all logic runs on synthetic data)
uv run pytest -q
```

The pytest suite (`tests/`) covers the money math (position-sizing clamp, R:R, ATR, portfolio heat, RS, order gates, journal, regime data-failure). The `-m src.data_provider <SYMBOL>` self-test verifies the live data layer end-to-end.

`--watchlist` = tickers already on the Robinhood "Swing Candidates" watchlist (evaluated first). `--new` = fresh tickers the agent found via web search (used to broaden, mainly when the watchlist is thin). Both are supplied by the routine agent, not hardcoded.

`--cash` (optional) = Robinhood buying power, which the routine agent should pass from `get_accounts` so per-trade sizing and the portfolio cash cap reflect reality. `--existing-risk` (optional) = open dollar-risk already in the book (Σ (entry−stop)×shares over current positions) so new orders respect the 6% portfolio-heat cap.

## Architecture

### Tier split (the core design decision)
The remote sandbox these scripts run in has a **network allowlist** and the **agent cannot fetch arbitrary URLs**, so work is divided by capability:
- **Python (this repo):** deterministic, price-derived math only — market regime, Stage 2 trend template, chart-pattern detection, position sizing, R:R. Emits JSON.
- **Routine agent (claude.ai prompts):** everything requiring judgment or external reach — discovering candidate tickers (WebSearch), verifying fundamentals/earnings (WebSearch), resolving VIX (WebSearch), and executing orders + watchlist changes (Robinhood MCP).

The handoff is the JSON written by `run_*.py`: each candidate carries an `agent_action` of `PLACE_ORDER`, `ADD_TO_WATCHLIST`, `SKIP`, or `VERIFY_VIA_WEBSEARCH`, and `instructions_for_agent` pre-packages ready-to-place orders. The agent never recomputes the math; it acts on these fields.

### Data flow per run
Both `run_premarket.py` and `run_eod.py` are thin wrappers over `src.pipeline.run_analysis()` (the single source of truth for the run sequence; the only real differences between the two runs — framing, order time-in-force — live in the prompts). The sequence:

`pipeline.run_analysis()` → `market_regime.regime_and_benchmark()` (returns stance **and** the SPY DataFrame, reused for RS) → for each ticker `evaluate.evaluate_ticker()` → `rs.rank_candidates()` (rank by relative strength) → `portfolio.apply_portfolio_limits()` (demote orders past the 6% heat / cash caps) → `report.build_json_output()` → `journal.record_run()` (append durable JSONL).

`evaluate_ticker` does **one** `get_history()` fetch and threads that DataFrame through `stage2`, `patterns`, `rs`, and `risk_engine` so each ticker costs a single API call (important for the rate limit).

### Data provider (`src/data_provider.py`)
All OHLCV comes from the **Twelve Data REST API** (`api.twelvedata.com`). Notable behaviors:
- **Key is read at call time** via `_api_key()`, not at import, so a caller can set `os.environ` before the first fetch.
- **Throttled** to 8s between calls (`TWELVEDATA_MIN_INTERVAL`) to stay under the free tier's 8 req/min (800/day).
- **VIX is unavailable on the free tier** — `get_history("VIX")` returns None by design; the agent resolves VIX via web search instead.
- On failure it stores the raw API error in module-level `last_error` and returns None (so callers can distinguish a bad key from an unreachable host).
- Returns an ascending DataFrame with `Open/High/Low/Close/Volume`, keeping the rest of the codebase provider-agnostic. To swap providers, this is the only file to change.

### Strategy modules
- `market_regime.py` — SPY/QQQ 50/150/200 SMA structure + VIX → stance. **Degrades safely:** missing SPY/QQQ data → `DEFENSIVE` with `data_failure: true` + `blocked_reason` (a data outage is reported distinctly from a genuine bearish DEFENSIVE so a network blip is never mistaken for a market signal); missing VIX but healthy SMAs → `AGGRESSIVE_PENDING_VIX` (agent must confirm VIX). `regime_and_benchmark()` also returns the SPY DataFrame for RS reuse.
- `stage2.py` — Minervini 5-condition trend template; all must pass or the ticker is dropped.
- `patterns.py` — detects VCP, Bull Flag, Flat Base, Pullback-to-20EMA from OHLCV; returns the highest-priority match (order: VCP > Bull Flag > Flat Base > Pullback) with a buy pivot and `extended` flag. Cup & Handle is intentionally left to agent judgment.
- `rs.py` — relative strength vs SPY (weighted blend of 1/3/6-month trailing returns minus SPY's). `rank_candidates()` orders candidates 1..N (1 = strongest); used to prioritise which orders survive the portfolio heat cap.
- `risk_engine.py` — 1% risk sizing, fractional shares, R:R. **Position size is clamped** so notional never exceeds `min(MAX_POSITION_PCT × account, cash_available)` — a tight stop can otherwise demand more shares than the whole account holds. `atr()` / `atr_stop()` provide ATR(14)-based stops; `estimate_targets()` derives T1/T2 from recent swing highs.
- `portfolio.py` — aggregate gate across a batch: keeps the strongest orders (by RS rank, then R:R) and demotes the rest to the watchlist once `MAX_PORTFOLIO_RISK_PCT` (6%) heat or available cash is exhausted (accounts for `existing-risk` already in the book).
- `journal.py` — appends one JSONL line per recommendation to `JOURNAL_PATH` (default repo `journal/trades.jsonl`, **not** /tmp). The durable feedback substrate for future outcome-grading; `outcome` is left null for a later grading pass.
- `evaluate.py` — orchestrates the above into one `agent_action` per ticker. Stop = the wider of the structural SMA50 stop (fallback 8%) and an ATR-based stop, so a stop hugging the entry can't oversize or whipsaw. **A `PLACE_ORDER` now requires** volume confirmation, price within 25% of the 52-week high, and R:R ≥ 2.0 — otherwise it demotes to the watchlist. A liquidity floor (`MIN_PRICE`, `MIN_AVG_DOLLAR_VOLUME`) skips thin names. Fundamentals are deliberately NOT checked here (Twelve Data free tier is price-only) — `fundamentals_unverified: true` signals the agent to verify before buying.
- `pipeline.py` — the shared run sequence both entry points call.
- `config.py` — all thresholds (risk %, R:R minimums, pivot/extended bands, ATR, RS horizons, liquidity floors, journal path). `load_dotenv()` runs here.

### Routine-prompt obligations (the unversioned half — keep these in sync)
The JSON now carries a stronger contract the prompt MUST honour:
- **Place the protective stop.** Each `place_orders[*]` entry carries `stop_loss_price`; after a buy fills, the prompt must immediately place that as a *separate* stop order and verify on each run that every open position still has a live stop. Python can only advise — it cannot place orders.
- **Earnings gate.** Skip any order with earnings within ~5 trading days (use a fundamentals/earnings source via WebSearch or MCP).
- **Feed account state back in.** Pass `--cash` (from `get_accounts`) and `--existing-risk` (Σ open risk from `get_equity_positions`) so sizing and the heat cap are real, not blind.

### Reporting (`send_report.py`)
Standalone CLI (not imported by the analysis pipeline) that emails a plain-text report via the **Resend API** (`api.resend.com`). The routine's final step writes the agent's composed briefing to a file and calls this. Reads `RESEND_API_KEY` inline (same contract as the data key). Without a verified Resend domain it sends from `onboarding@resend.dev` and only to the account owner's email. The routines email on every run (including DEFENSIVE / key-failure) so a missing email is itself a signal.

## Environment gotchas (these have caused real failures)

- **Pass the API key inline, never via `export` or `.env`.** Each Bash call in the routine is a fresh shell, so `export` doesn't persist, and `printf`-ing a `.env` is fragile (escaped `\n` corrupted the key in practice). Inline `TWELVEDATA_API_KEY=… uv run …` sets it for that one process reliably. `data_provider` also calls `load_dotenv()` as a secondary path, but inline is the contract.
- **The sandbox must allowlist every external host.** The Default cloud environment blocks outbound HTTPS to non-allowlisted hosts. Required domains, added under Network access → Custom (with "include default package managers" checked so PyPI/GitHub still work): `api.twelvedata.com` (market data) and `api.resend.com` (email). If a run reports `Host not in allowlist`, that domain is missing or the change hasn't propagated to a new session.
- **A false `DEFENSIVE` usually means the key didn't reach Python.** If a briefing shows "SPY/QQQ data unavailable" alongside DEFENSIVE/0-6, the key was missing or invalid — re-run the Step 1 diagnostic before trusting any stance.
- **Don't put the API key in the environment's "Environment variables" box** — that field is documented as visible to anyone using the environment.
