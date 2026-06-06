import os
from dotenv import load_dotenv

load_dotenv()

ACCOUNT_SIZE = float(os.getenv("ACCOUNT_SIZE", 500))
RISK_PER_TRADE_PCT = 0.01
MAX_PORTFOLIO_RISK_PCT = 0.06
RISK_PER_TRADE = ACCOUNT_SIZE * RISK_PER_TRADE_PCT  # $5

# VIX stance thresholds
VIX_AGGRESSIVE_MAX = 20
VIX_SELECTIVE_MAX = 25
VIX_DEFENSIVE_MAX = 30

# Stage 2
MIN_ABOVE_52W_LOW_PCT = 0.30

# Pattern thresholds
EXTENDED_ABOVE_PIVOT_PCT = 0.05   # >5% above pivot = extended, don't chase
BUY_SIGNAL_THRESHOLD_PCT = 0.02   # within 2% above pivot = READY TO BUY

# Risk / reward
MIN_RR = 2.0
PREFERRED_RR = 3.0
MAX_POSITION_PCT = 0.20           # hard cap: a single position may not exceed 20% of account

# ATR-based stops
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 2.0         # stop = entry - ATR_STOP_MULTIPLIER * ATR(14)

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
