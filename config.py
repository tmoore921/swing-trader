import os
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", 500))
RISK_PER_TRADE_PCT = 0.01
# Raised 2026-09 from 0.06 → 0.08 so the book can carry ~8 concurrent 1%-risk
# positions instead of 6. This is the one loosened knob that raises max
# drawdown; drop it back to 0.06 to restore the old ceiling.
MAX_PORTFOLIO_RISK_PCT = 0.08
RISK_PER_TRADE = ACCOUNT_SIZE * RISK_PER_TRADE_PCT  # $5

# VIX stance thresholds
VIX_AGGRESSIVE_MAX = 20
VIX_SELECTIVE_MAX = 25
VIX_DEFENSIVE_MAX = 30

# Stage 2
MIN_ABOVE_52W_LOW_PCT = 0.30

# Pattern thresholds
EXTENDED_ABOVE_PIVOT_PCT = 0.07   # >7% above pivot = extended, don't chase
# A VCP's volume is "confirmed" by dry-up through the base OR expansion on the
# breakout week; this is the multiple of base-average volume that counts as
# expansion. See patterns._check_vcp.
VOLUME_EXPANSION_RATIO = 1.10

# --- Order trigger band ----------------------------------------------------
# Orders are LIMIT buys placed AT the pivot, so the order can be queued while
# price is still below the pivot (it fills on the breakout) and up to the
# extended threshold above it. Widened 2026-06 — the old 0..+2% band was so
# narrow that breakouts were almost never caught mid-window, so nothing fired.
# Widened again 2026-09: a month of live runs showed names sitting 4-6% below
# the pivot (e.g. LLY at -5.4%) falling out of the band the day before they ran.
BUY_ZONE_BELOW_PIVOT_PCT = 0.07   # place the limit buy when within 7% BELOW pivot
BUY_SIGNAL_THRESHOLD_PCT = 0.07   # ...up to 7% ABOVE pivot (>7% = extended, don't chase)

# --- Order quality gates (toggle to open/close the funnel) -----------------
# These are the gates a setup must clear to become a PLACE_ORDER (vs demote to
# watchlist). Flip a REQUIRE_* to False to loosen.
#
# REQUIRE_VOLUME_CONFIRMATION turned OFF 2026-09. It was the single largest
# blocker in live runs: 4 of 12 candidates on 2026-09-08 (XOM, NVDA, MPC, VLO)
# cleared every other gate and were rejected on this alone. The underlying
# volume_ok test also fought the strategy — it demanded volume still be
# *contracting* into the current week, which is the opposite of what a genuine
# breakout looks like (see the widened test in patterns._check_vcp). Volume is
# still computed and reported, it just no longer vetoes an order.
REQUIRE_VOLUME_CONFIRMATION = False  # pattern volume dry-up/expansion: report, don't veto
REQUIRE_NEAR_52W_HIGH = True         # price must be within NEAR_52W_HIGH_PCT of the 52w high
NEAR_52W_HIGH_PCT = 0.30             # "near the high" = within 30% of the 52-week high

# Risk / reward
# MIN_RR lowered 2.0 → 1.5 (2026-09) alongside the estimate_targets fix. With a
# realistic T1 a 1.5R first target on a Stage 2 breakout is a reasonable trade,
# and T2/trailing carries the rest of the upside.
MIN_RR = 1.5
PREFERRED_RR = 2.5
MAX_POSITION_PCT = 0.20           # hard cap: a single position may not exceed 20% of account

# --- Stop width ------------------------------------------------------------
# evaluate.py takes the WIDER of the structural (SMA50) and ATR stops so a stop
# hugging the entry can't oversize or whipsaw. Unbounded, that produced 17%-wide
# stops (XOM 2026-09-08: entry $384, stop $317), which inflates risk-per-share
# and crushes R:R. Cap how far a stop may sit below entry; beyond this the setup
# is simply too loose to trade at this account size.
MAX_STOP_DISTANCE_PCT = 0.10      # a stop may sit at most 10% below entry

# --- Options screening -----------------------------------------------------
# Twelve Data's free tier has no option chains/greeks, so Python only emits the
# *structure* of an options play (expiration window, target strike/delta, premium
# budget, exit tied to the stock stop). The routine agent fetches the live chain
# via the Robinhood MCP, prices it, and places the order — same tier split as
# everything else. Set OPTIONS_ENABLED=False to drop options from the output.
OPTIONS_ENABLED = True
OPTIONS_MIN_DTE = 30              # shortest acceptable days-to-expiry (theta control)
OPTIONS_TARGET_DTE = 45          # preferred expiry for a multi-week swing
OPTIONS_MAX_DTE = 60             # longest acceptable days-to-expiry
OPTIONS_TARGET_DELTA = 0.65      # slightly-ITM directional call: leverage w/ less theta than OTM
OPTIONS_MAX_PREMIUM_PCT = 0.15   # max premium outlay per position as % of account (defined risk)
OPTIONS_MAX_SPREAD_PCT = 0.15    # agent liquidity gate: skip if bid/ask spread > 15% of mid

# --- Options affordability pre-filter --------------------------------------
# A contract is 100 shares, so its cost is ~(premium per share × 100). A
# slightly-ITM 30-60 DTE call typically runs a few percent of spot: MRK at ~$148
# quoted $6.20/share on 2026-09-08 = 4.2% of spot = $620 per contract, against a
# $75 budget. At this account size that is the norm, not the exception — so
# estimate the cost here and mark the blueprint rather than making the agent
# fetch a chain per ticker only to skip it. Raise OPTIONS_MAX_PREMIUM_PCT or
# trade cheaper underlyings to make calls reachable.
OPTIONS_TYPICAL_PREMIUM_PCT_OF_SPOT = 0.05
OPTIONS_CONTRACT_MULTIPLIER = 100

# ATR-based stops
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0         # stop = entry - ATR_STOP_MULTIPLIER * ATR(14)

# --- Target estimation (T1/T2) ---------------------------------------------
# T1 is the nearest real swing-high resistance above entry. "Swing high" means a
# fractal pivot — a bar higher than SWING_PIVOT_BARS bars on both sides — not any
# daily high, which is what the old code used and why R:R came out near zero.
SWING_PIVOT_BARS = 3              # bars either side that a pivot high must dominate
RESISTANCE_LOOKBACK_BARS = 120    # how far back to look for overhead supply
MIN_RESISTANCE_DISTANCE_PCT = 0.03  # closer than 3% above entry = breakout noise, not resistance
MEASURED_MOVE_R = 2.5             # no overhead supply (new-high breakout) → T1 = entry + 2.5R

# Relative strength (vs SPY). Weighted blend of trailing returns.
RS_HORIZONS = {21: 0.4, 63: 0.4, 126: 0.2}   # ~1mo, 3mo, 6mo trading days → weights

# Liquidity floor — skip thinly traded names a small account can't exit cleanly
MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME = 5_000_000   # 20-day avg (close * volume)

# Trade journal — durable path (NOT /tmp, which the sandbox wipes between runs)
import os as _os
JOURNAL_PATH = _os.getenv(
    "SWING_JOURNAL_PATH",
    _os.path.join(_os.path.dirname(__file__), "journal", "trades.jsonl"),
)
