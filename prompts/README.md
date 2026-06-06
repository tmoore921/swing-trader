# Routine prompts (the unversioned half, now versioned)

These two files are the **claude.ai scheduled-routine prompts** that drive the
Python analysis engine in this repo. They were previously only editable in the
claude.ai routine UI and never tracked. Keep them here so changes are diffable,
and **keep them in sync with the code** — a strategy change usually touches both.

## Files
- `premarket_routine.md` — fires ~8:30 AM ET, Mon–Fri (GFD limit orders).
- `eod_routine.md` — fires ~3:30 PM ET, Mon–Fri (GTC limit orders); also the
  primary exit-management pass.

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
