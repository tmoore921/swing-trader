"""Market data provider — Twelve Data REST API.

Free tier: 800 requests/day, 8 requests/minute, no cost.
Set the API key via the TWELVEDATA_API_KEY environment variable.
Returns pandas DataFrames with Open/High/Low/Close/Volume indexed ascending by date,
so the rest of the codebase is provider-agnostic.
"""

import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

# Load .env so the API key is picked up even when the caller didn't export it
# into the current shell (each Bash call in the routine is a fresh shell).
load_dotenv()

API_KEY = os.getenv("TWELVEDATA_API_KEY", "demo")
BASE_URL = "https://api.twelvedata.com"

# Stay under the 8 req/min free-tier limit (≈7.5s minimum spacing → use 8s).
_MIN_INTERVAL = float(os.getenv("TWELVEDATA_MIN_INTERVAL", "8"))
_last_call_ts = 0.0

# Symbols that need remapping for Twelve Data
SYMBOL_MAP = {
    "^VIX": "VIX",
    "VIX": "VIX",
}


def _throttle():
    global _last_call_ts
    elapsed = time.time() - _last_call_ts
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_call_ts = time.time()


def get_history(ticker: str, outputsize: int = 500) -> pd.DataFrame | None:
    """Fetch daily OHLCV history. Returns ascending DataFrame or None on failure.

    outputsize=500 ≈ 2 trading years, enough for the 200-day SMA in Stage 2.
    """
    symbol = SYMBOL_MAP.get(ticker, ticker)
    _throttle()
    try:
        resp = requests.get(
            f"{BASE_URL}/time_series",
            params={
                "symbol": symbol,
                "interval": "1day",
                "outputsize": outputsize,
                "order": "ASC",
                "apikey": API_KEY,
            },
            timeout=30,
        )
        data = resp.json()
        if data.get("status") != "ok" or "values" not in data:
            return None

        df = pd.DataFrame(data["values"])
        if df.empty:
            return None

        rename = {
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume",
        }
        for src, dst in rename.items():
            if src in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
            else:
                df[dst] = pd.NA

        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime").sort_index()
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    except Exception:
        return None


def latest_close(ticker: str) -> float | None:
    """Convenience: most recent close price."""
    df = get_history(ticker, outputsize=5)
    if df is None or df.empty:
        return None
    return round(float(df["Close"].iloc[-1]), 2)


def api_key_configured() -> bool:
    return API_KEY not in ("", "demo", None)
