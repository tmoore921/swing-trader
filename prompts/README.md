# Routine prompts (the unversioned half, now versioned)

These two files are the **claude.ai scheduled-routine prompts** that drive the
Python analysis engine in this repo. They were previously only editable in the
claude.ai routine UI and never tracked. Keep them here so changes are diffable,
and **keep them in sync with the code** — a strategy change usually touches both.

## Files
- `premarket_routine.md` — fires ~8:30 AM ET, Mon–Fri (GFD limit orders).
- `eod_routine.md` — fires ~3:30 PM ET, Mon–Fri (GTC limit orders); also the
  primary exit-management pass.

There is a **third live routine**, "Swing Trading — Mid-Day Check" (~12:00 PM ET),
which has no file here yet. It is a trimmed EOD pass whose main job is catching
positions that broke a stop or hit a target intraday; it is deliberately more
selective about new entries. Keep it in sync manually until it is versioned.

## How to deploy
1. Open the routine in claude.ai → edit the prompt.
2. Replace its body with the contents of the matching file here.
3. Fill the two placeholders: `{{TWELVEDATA_API_KEY}}` and `{{RESEND_API_KEY}}`
   (or wire them however your environment injects secrets — see the repo
   CLAUDE.md "Environment gotchas": pass inline, never via the env-vars box).
4. Set the recipient email in the `--to` of the final step.

## What changed vs. the old prompts (the new JSON contract)
- **Stops are now mandatory and reconciled.** Step 2 of every run checks that
  *every* open position has a live protective stop and places one if missing.
  This is the safety net for fills from the previous run.
- **Earnings gate.** No new entry if earnings fall within ~5 trading days.
- **Account state is fed back into the math.** Each run passes `--cash`
  (from `get_accounts`) and `--existing-risk` (Σ open risk from
  `get_equity_positions` + stop orders) so sizing and the 6% portfolio-heat cap
  are real, not blind.
- **Kill-switch.** Halt new entries on a data failure or an account drawdown
  breach (see each prompt's guard step).
- **Options screening (new).** Step 7b in each prompt acts on
  `instructions_for_agent.options_candidates` — defined-risk long-call blueprints
  for the same Stage 2 setups. Python emits the structure (expiry window, target
  strike/delta, premium budget, exit tied to the underlying stop); the agent
  prices the live chain via the Robinhood option MCP and places it. Per ticker:
  shares **or** the call, never both. The EOD run also manages open option
  positions (`get_option_positions`) in its Step 2 exit pass.
- **Wider order trigger.** The Python buy-zone band was widened (limit buys are now
  queued from ~7% below the pivot up to ~7% above) so breakouts are actually
  caught — the old 0..+2% window almost never fired. The gate knobs live in
  `config.py` (`BUY_ZONE_BELOW_PIVOT_PCT`, `BUY_SIGNAL_THRESHOLD_PCT`,
  `REQUIRE_VOLUME_CONFIRMATION`, `REQUIRE_NEAR_52W_HIGH`, `MIN_RR`).

## 2026-09 retune — why nothing was firing

A month of live runs placed **zero** orders. Re-running 2026-09-08's watchlist
locally showed 10 of 12 names inside the buy zone and every one of them rejected.
Three causes, in order of impact:

1. **`estimate_targets` was broken.** T1 was the *lowest daily high* more than 2%
   above entry over 60 bars. For a stock coiling under its pivot that is ~2-4%
   away, producing R:R of 0.16–0.49. Names that *passed* R:R scored exactly 2.0
   because no bar cleared entry+2% and they hit the hardcoded fallback — i.e. the
   R:R gate only ever passed when the target was unknown. T1 now uses genuine
   fractal swing-high pivots at least `MIN_RESISTANCE_DISTANCE_PCT` above entry,
   falling back to a `MEASURED_MOVE_R` measured move at true new highs.
2. **Volume confirmation fought the strategy.** The VCP test demanded volume still
   be *contracting into the current week* — the opposite of a breakout. It alone
   rejected 4 clean setups (XOM, NVDA, MPC, VLO). It now accepts base dry-up **or**
   breakout expansion, and `REQUIRE_VOLUME_CONFIRMATION` defaults to `False`
   (reported, not vetoed).
3. **Stops ran unbounded wide.** Taking the wider of the SMA50 and ATR stops hit
   17% below entry (XOM), inflating risk-per-share and crushing R:R. Now capped at
   `MAX_STOP_DISTANCE_PCT`.

Knobs loosened alongside the fixes: `MIN_RR` 2.0 → 1.5, buy zone ±4/5% → ±7%,
`NEAR_52W_HIGH_PCT` 25% → 30%, `MAX_PORTFOLIO_RISK_PCT` 6% → 8%.

Net effect on that same watchlist: **0 orders → 4 orders** (MRK, NVDA, MPC, VLO),
with 8 of 12 still correctly rejected. Note that every order that now fires does so
via the measured-move fallback at exactly `MEASURED_MOVE_R`, so in practice
`MEASURED_MOVE_R` — not `MIN_RR` — sets the R:R of a new-high breakout entry.
