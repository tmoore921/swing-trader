# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A swing-trading analysis engine that runs as the Python half of a two-tier automated trading system. It is driven by two scheduled Claude Code "routines" (remote CCR agents) that fire pre-market (~8:30 AM ET) and end-of-day (~3:30 PM ET), Mon–Fri, against a small (~$500) Robinhood account.

**Critical:** this repo is only one half of the system. The other half — ticker discovery, fundamental verification, VIX lookup, and all order/watchlist execution — lives in the **routine prompts on claude.ai**, not in this repo. Those prompts run the scripts here, read the JSON output, and act on it via the Robinhood MCP. Changing strategy behavior often means editing **both** the Python here **and** the two routine prompts. The repo does not contain or call any Robinhood/order code.

## Commands

```bash
uv sync                                          # install deps (uses uv, creates .venv with Python 3.11+)

# Run analysis — the API key MUST be passed inline (see "Why inline" below)
TWELVEDATA_API_KEY=<key> uv run python run_premarket.py --watchlist AAPL,MSFT --new NVDA,AVGO --output /tmp/swing_premarket.json
TWELVEDATA_API_KEY=<key> uv run python run_eod.py       --watchlist AAPL,MSFT --new NVDA,AVGO --output /tmp/swing_eod.json

# Data-layer diagnostic — prints "OK — SPY returned N rows" or "FAILED — <raw API reason>"
TWELVEDATA_API_KEY=<key> uv run python -m src.data_provider SPY
```

There is no test suite, linter, or build step configured. The `-m src.data_provider <SYMBOL>` self-test is the primary way to verify the data layer end-to-end.

`--watchlist` = tickers already on the Robinhood "Swing Candidates" watchlist (evaluated first). `--new` = fresh tickers the agent found via web search (used to broaden, mainly when the watchlist is thin). Both are supplied by the routine agent, not hardcoded.

## Architecture

### Tier split (the core design decision)
The remote sandbox these scripts run in has a **network allowlist** and the **agent cannot fetch arbitrary URLs**, so work is divided by capability:
- **Python (this repo):** deterministic, price-derived math only — market regime, Stage 2 trend template, chart-pattern detection, position sizing, R:R. Emits JSON.
- **Routine agent (claude.ai prompts):** everything requiring judgment or external reach — discovering candidate tickers (WebSearch), verifying fundamentals/earnings (WebSearch), resolving VIX (WebSearch), and executing orders + watchlist changes (Robinhood MCP).

The handoff is the JSON written by `run_*.py`: each candidate carries an `agent_action` of `PLACE_ORDER`, `ADD_TO_WATCHLIST`, `SKIP`, or `VERIFY_VIA_WEBSEARCH`, and `instructions_for_agent` pre-packages ready-to-place orders. The agent never recomputes the math; it acts on these fields.

### Data flow per run
`run_premarket.py` / `run_eod.py` → `market_regime.check_market_regime()` → for each ticker `evaluate.evaluate_ticker()` → `report.build_json_output()`. `evaluate_ticker` does **one** `get_history()` fetch and threads that DataFrame through `stage2`, `patterns`, and `risk_engine` so each ticker costs a single API call (important for the rate limit). The two run scripts are near-identical; differences are framing and order time-in-force (pre-market GFD vs EOD GTC) — those live in the prompts, not the code.

### Data provider (`src/data_provider.py`)
All OHLCV comes from the **Twelve Data REST API** (`api.twelvedata.com`). Notable behaviors:
- **Key is read at call time** via `_api_key()`, not at import, so a caller can set `os.environ` before the first fetch.
- **Throttled** to 8s between calls (`TWELVEDATA_MIN_INTERVAL`) to stay under the free tier's 8 req/min (800/day).
- **VIX is unavailable on the free tier** — `get_history("VIX")` returns None by design; the agent resolves VIX via web search instead.
- On failure it stores the raw API error in module-level `last_error` and returns None (so callers can distinguish a bad key from an unreachable host).
- Returns an ascending DataFrame with `Open/High/Low/Close/Volume`, keeping the rest of the codebase provider-agnostic. To swap providers, this is the only file to change.

### Strategy modules
- `market_regime.py` — SPY/QQQ 50/150/200 SMA structure + VIX → stance. **Degrades safely:** missing SPY/QQQ data → `DEFENSIVE` (no trades); missing VIX but healthy SMAs → `AGGRESSIVE_PENDING_VIX` (agent must confirm VIX).
- `stage2.py` — Minervini 5-condition trend template; all must pass or the ticker is dropped.
- `patterns.py` — detects VCP, Bull Flag, Flat Base, Pullback-to-20EMA from OHLCV; returns the highest-priority match (order: VCP > Bull Flag > Flat Base > Pullback) with a buy pivot and `extended` flag. Cup & Handle is intentionally left to agent judgment.
- `risk_engine.py` — $5 (1%) risk sizing, fractional shares, R:R; `estimate_targets()` derives T1/T2 from recent swing highs as a starting point.
- `evaluate.py` — orchestrates the above into one `agent_action` per ticker. Stop defaults to SMA50 (fallback 8% below entry). Fundamentals are deliberately NOT checked here (Twelve Data free tier is price-only) — `fundamentals_unverified: true` signals the agent to verify before buying.
- `config.py` — all thresholds (risk %, R:R minimums, pivot/extended bands). `load_dotenv()` runs here.

## Environment gotchas (these have caused real failures)

- **Pass the API key inline, never via `export` or `.env`.** Each Bash call in the routine is a fresh shell, so `export` doesn't persist, and `printf`-ing a `.env` is fragile (escaped `\n` corrupted the key in practice). Inline `TWELVEDATA_API_KEY=… uv run …` sets it for that one process reliably. `data_provider` also calls `load_dotenv()` as a secondary path, but inline is the contract.
- **The sandbox must allowlist `api.twelvedata.com`.** The Default cloud environment blocks outbound HTTPS to non-allowlisted hosts. The domain is added under the environment's Network access → Custom (with "include default package managers" checked so PyPI/GitHub still work). If a run reports `Host not in allowlist`, that setting was lost or the change hasn't propagated to a new session.
- **A false `DEFENSIVE` usually means the key didn't reach Python.** If a briefing shows "SPY/QQQ data unavailable" alongside DEFENSIVE/0-6, the key was missing or invalid — re-run the Step 1 diagnostic before trusting any stance.
- **Don't put the API key in the environment's "Environment variables" box** — that field is documented as visible to anyone using the environment.
