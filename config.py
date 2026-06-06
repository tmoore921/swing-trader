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
MAX_POSITION_PCT = 0.20           # warn if position > 20% of account
